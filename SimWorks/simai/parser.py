import asyncio
import inspect
import json
import logging
from logging import DEBUG
from logging import WARNING
from typing import List
from typing import Optional
from typing import Tuple

from django.db.models import QuerySet

from .models import ResponseType
from asgiref.sync import sync_to_async
from chatlab.models import Message
from chatlab.models import RoleChoices
from simcore.models import Simulation, SimulationMetadata
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class StructuredOutputParser:
    """
    A utility class responsible for parsing the OpenAI structured output into metadata and messages...
    """

    def __init__(self, simulation: Simulation, system_user: User, response):
        self.simulation = simulation
        self.system_user = system_user
        self.response = response

    async def parse_output(self, output: dict or str, response_type: ResponseType = ResponseType.REPLY) -> List[
        Message]:
        func_name = inspect.currentframe().f_code.co_name

        logger.debug(f"output_text: {output}")

        if isinstance(output, str):
            output = json.loads(output)

        # If it's a full OpenAI response, merge all assistant message outputs
        if isinstance(output, dict) and "output" in output:
            assistant_messages = output["output"]
            output_chunks = []

            for msg in assistant_messages:
                for part in msg.get("content") or []:
                    if part.get("type") == "output_text":
                        try:
                            parsed = json.loads(part["content"])
                            output_chunks.append(parsed)
                        except json.JSONDecodeError as e:
                            logger.warning(f"[{func_name}] Failed to parse part: {e}")

            # Merge messages and metadata
            merged_output = {"messages": [], "metadata": {"patient_metadata": {}, "simulation_metadata": []}}
            for chunk in output_chunks:
                merged_output["messages"].extend(chunk.get("messages") or [])
                metadata = chunk.get("metadata") or {}

                # Merge patient_metadata
                if "patient_metadata" in metadata:
                    merged_output["metadata"]["patient_metadata"].update(metadata["patient_metadata"])

                # Extend simulation_metadata list
                if "simulation_metadata" in metadata:
                    merged_output["metadata"]["simulation_metadata"].extend(
                        metadata["simulation_metadata"]
                    )

            output = merged_output

        if response_type is ResponseType.FEEDBACK:
            await self.log(func_name, f"Feedback Output: {output}")
            await self._parse_metadata(output, response_type.label)
            return []

        # Now handle normal parsing flow
        messages = output.get("messages") or []
        metadata = output.get("metadata") or {}

        # Gracefully handle missing or null metadata blocks
        patient_data = metadata.get("patient_metadata") or {}
        simulation_data = metadata.get("simulation_metadata") or {}
        scenario_data = metadata.get("scenario_metadata") or {}
        patient_history = patient_data.get("medical_history") or {}
        patient_metadata = {
            k: v for k, v in patient_data.items() if k not in ("medical_history", "additional")
        }
        patient_metadata.update(patient_data.get("additional_metadata") or {})

        logger.debug(f"{func_name} parsed {len(messages)} messages")
        logger.debug(f"{func_name} simulation_data {type(simulation_data)}: {simulation_data}")

        metadata_tasks = []
        if patient_metadata:
            metadata_tasks.append(self._parse_metadata(patient_metadata, "patient metadata"))
        if patient_history:
            metadata_tasks.append(self._parse_metadata(patient_history, "patient history"))
        if simulation_data:
            metadata_tasks.append(self._parse_metadata(simulation_data, "simulation metadata"))
        if scenario_data:
            await self._parse_scenario_attribute(scenario_data)

        await asyncio.gather(*metadata_tasks)
        message_tasks = [self._parse_message(m) for m in messages]
        return await asyncio.gather(*message_tasks)

    async def _parse_message(self, message: dict) -> Optional[Message]:
        func_name = inspect.currentframe().f_code.co_name
        await self.log(func_name, f"received input: {message}")

        display_name = getattr(self.simulation, "sim_patient_display_name", "Unknown")

        return await sync_to_async(Message.objects.create)(
            simulation=self.simulation,
            content=message["content"],
            sender=self.system_user,
            display_name=display_name,
            role=RoleChoices.ASSISTANT,
            openai_id=self.response.id,
            response=self.response,
        )

    async def _parse_metadata(self, metadata: dict, attribute: str) -> None:
        """
        Processes a metadata structure and creates SimulationMetadata objects.

        If metadata is a dict, it iterates over its key/value pairs.
        If it is a list, it iterates over each element (which should be dicts) and
        then over each key/value pair inside them.

        :param metadata: A dict or list containing the metadata.
        :param attribute: A string describing the type of metadata (e.g., "patient history").
        """
        func_name = inspect.currentframe().f_code.co_name
        logger.debug(f"[{func_name}] received input ({type(metadata)}): {metadata}")

        if isinstance(metadata, dict):
            # Process key-value pairs from the dict
            for key, value in metadata.items():
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value)
                else:
                    value_str = str(value)
                metafield = await sync_to_async(SimulationMetadata.objects.create)(
                    simulation=self.simulation,
                    key=key.lower().replace("_", " "),
                    value=value_str,
                    attribute=attribute,
                )
                await self.log(
                    func_name, f"... new metafield created: {metafield.key}", DEBUG
                )
        elif isinstance(metadata, list):
            # Process each dictionary in the list
            for index, item in enumerate(metadata):
                if isinstance(item, dict):
                    for key, value in item.items():
                        if isinstance(value, (dict, list)):
                            value_str = json.dumps(value)
                        else:
                            value_str = str(value)
                        # Append index to key for uniqueness if needed
                        metafield = await sync_to_async(
                            SimulationMetadata.objects.create
                        )(
                            simulation=self.simulation,
                            key=f"Condition #{index} {key.lower().replace("_", " ")}",
                            value=value_str,
                            attribute=attribute,
                        )
                        await self.log(
                            func_name,
                            f"... new metafield created: {metafield.key}",
                            DEBUG,
                        )
                else:
                    await self.log(
                        func_name,
                        f"Expected a dict in metadata list, but got {type(item)}",
                        WARNING,
                    )
        else:
            logger.warning(
                func_name,
                f"Expected metadata to be a dict or list, but got {type(metadata)}",
                WARNING,
            )

    async def _parse_scenario_attribute(self, attributes: dict) -> None:
        """
        Validates and applies scenario attributes to this simulation.
        Accepts a dict with optional 'diagnosis' and 'chief_complaint' keys.

        Raises:
            TypeError: if input is not a dict-like object.
            ValueError: if an unknown key is encountered.
        """
        if not isinstance(attributes, dict):
            try:
                attributes = dict(attributes)
            except Exception:
                raise TypeError("Scenario attributes must be a dict or convertible to dict.")

        allowed_keys = {"diagnosis", "chief_complaint"}
        unknown_keys = set(attributes) - allowed_keys
        updated_fields = []

        if unknown_keys:
            raise ValueError(f"Unknown scenario attribute(s): {', '.join(unknown_keys)}")

        for k, v in attributes.items():
            if k in allowed_keys:
                setattr(self.simulation, k, v)
                updated_fields.append(k)
            else:
                logger.warning(f"Ignored unknown scenario attribute: {k}={v}")

        if updated_fields:
            await sync_to_async(self.simulation.save)(update_fields=updated_fields)


    @staticmethod
    async def log(func_name, msg="triggered", level=DEBUG) -> None:
        return logger.log(level, f"[{func_name}]: {msg}")