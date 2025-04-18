import json
import logging
from datetime import datetime
from datetime import timedelta
from hashlib import sha256

from SimManAI.models import Response, Prompt
from SimManAI.prompts import get_or_create_prompt

from core.utils import randomize_display_name
from django.conf import settings
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class RoleChoices(models.TextChoices):
    USER = "U", _("user")
    ASSISTANT = "A", _("assistant")


class SimulationManager(models.Manager):
    def create(self, **kwargs):
        user = kwargs.get("user")
        prompt = kwargs.get("prompt")

        if not prompt:
            if not user:
                raise ValueError("Cannot auto-generate prompt without user.")
            role = getattr(user, "role", None)
            kwargs["prompt"] = get_or_create_prompt(app_label="ChatLab", role=role)

        return super().create(**kwargs)

class Simulation(models.Model):
    start_timestamp = models.DateTimeField(auto_now_add=True)
    end_timestamp = models.DateTimeField(blank=True, null=True)
    objects = SimulationManager()
    time_limit = models.DurationField(
        blank=True, null=True, help_text="Optional max duration for this simulation"
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    openai_model = models.CharField(blank=True, null=True, max_length=128)
    metadata_checksum = models.CharField(max_length=64, blank=True, null=True)
    prompt = models.ForeignKey(
        Prompt,
        on_delete=models.RESTRICT,
        null=False,
        blank=False,
        help_text=_("The prompt to use as AI instructions."),
    )

    description = models.TextField(blank=True, null=True)
    sim_patient_full_name = models.CharField(max_length=100, blank=True)
    sim_patient_display_name = models.CharField(max_length=100, blank=True)

    @property
    def sim_patient_initials(self):
        parts = self.sim_patient_display_name.strip().split()
        if not parts:
            return "Unk"

        if len(parts) == 1:
            return parts[0][0].upper()

        # Use first and last word initials if more than one word
        return f"{parts[0][0].upper()}{parts[-1][0].upper()}"

    diagnosis = models.TextField(blank=True, null=True, max_length=100)

    @property
    def in_progress(self) -> bool:
        """Return if simulation is in progress"""
        return self.end_timestamp is None or self.end_timestamp < datetime.now()

    @property
    def is_complete(self) -> bool:
        """Return if simulation has already completed."""
        return self.end_timestamp is not None or (
                self.time_limit and now() > self.start_timestamp + self.time_limit
        )

    @property
    def is_ended(self):
        return self.is_complete

    @property
    def is_timed_out(self):
        return bool(self.time_limit and now() > self.start_timestamp + self.time_limit)

    @property
    def length(self) -> timedelta or None:
        """Return timedelta from simulation start_timestamp to finish, or None if not ended"""
        if self.start_timestamp and self.end_timestamp:
            return self.end_timestamp - self.start_timestamp
        return None

    @property
    def history(self) -> list:
        """Return message history for simulation"""
        _history = []
        messages = Message.objects.filter(simulation=self.pk, order__gt=0).order_by(
            "-order"
        )
        for message in messages:
            _history.append(
                {"role": message.get_role_display(), "content": message.content}
            )
        return _history

    def end(self):
        self.end_timestamp = now()
        self.save()
        self.generate_feedback()

    def generate_feedback(self):
        from asgiref.sync import async_to_sync
        from SimManAI.async_client import AsyncOpenAIChatService

        service = AsyncOpenAIChatService()
        async_to_sync(service.generate_simulation_feedback)(self)

    def calculate_metadata_checksum(self) -> str:
        # Get sorted list of (key, value) pairs
        data = list(self.metadata.values_list("key", "value").order_by("key"))
        encoded = json.dumps(data)
        return sha256(encoded.encode("utf-8")).hexdigest()

    @classmethod
    def create_with_default_prompt(cls, user, app_label="ChatLab", **kwargs):
        """
        Create a Simulation with a default prompt based on the user role and app_label.
        """
        from SimManAI.prompts import get_or_create_prompt

        prompt = get_or_create_prompt(app_label=app_label, role=user.role)
        return cls.objects.create(user=user, prompt=prompt, **kwargs)

    def save(self, *args, **kwargs):
        # Ensure prompt is set based on user.role if not already provided
        if not self.prompt:
            if not self.user:
                raise ValueError("Cannot assign default prompt without a user.")
            self.prompt = get_or_create_prompt(app_label="ChatLab", role=getattr(self.user, "role", None))

        # Handle display name update if full name is changed
        updating_name = False
        if self.pk:
            old = Simulation.objects.get(pk=self.pk)
            updating_name = old.sim_patient_full_name != self.sim_patient_full_name
        else:
            updating_name = bool(self.sim_patient_full_name)

        if updating_name:
            self.sim_patient_display_name = randomize_display_name(self.sim_patient_full_name)

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.description:
            return f"ChatLab Sim #{self.pk}: {self.description}"
        else:
            return f"ChatLab Sim #{self.pk}"


class SimulationMetadata(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    simulation = models.ForeignKey(
        Simulation, on_delete=models.CASCADE, related_name="metadata"
    )
    key = models.CharField(blank=False, null=False, max_length=255)
    attribute = models.CharField(blank=False, null=False, max_length=64)
    value = models.CharField(blank=False, null=False, max_length=2000)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        self.simulation.metadata_checksum = (
            self.simulation.calculate_metadata_checksum()
        )
        self.simulation.save(update_fields=["metadata_checksum"])

    def __str__(self):
        return (
            f"Sim#{self.simulation.id} Metadata ({self.attribute.lower()}): {self.key.title()} "
            f""
        )


class Message(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField(blank=True, null=True)
    role = models.CharField(
        max_length=2,
        choices=RoleChoices.choices,
        default=RoleChoices.USER,
    )

    is_read = models.BooleanField(default=False)
    order = models.PositiveIntegerField(editable=False, null=True, blank=True)
    response = models.ForeignKey(
        "SimManAI.Response",
        on_delete=models.CASCADE,
        verbose_name="OpenAI Response",
        related_name="messages",
        null=True,
        blank=True,
    )
    openai_id = models.CharField(null=True, blank=True, max_length=255)
    display_name = models.CharField(max_length=100, blank=True)

    def set_openai_id(self, openai_id):
        self.openai_id = openai_id
        self.save(update_fields=["openai_id"])

    def get_previous_openai_id(self) -> str or None:
        """Return most recent OpenAI response_ID in current simulation"""
        previous_message = (
            Message.objects.filter(
                simulation=self.simulation,
                order__lt=self.order,
                role=RoleChoices.ASSISTANT,  # Only consider ASSISTANT messages
                openai_id__isnull=False,  # That have an openai_id set
            )
            .order_by("-order")
            .first()
        )
        return previous_message.openai_id if previous_message else None

    def get_openai_input(self) -> dict:
        """Return list formatted for OpenAI Responses API input."""
        return {
            "role": self.get_role_display(),
            "content": self.content,
        }

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if self.order is None:
            last_message = (
                Message.objects.filter(simulation=self.simulation)
                .order_by("-order")
                .first()
            )
            self.order = (
                last_message.order + 1
                if last_message and last_message.order is not None
                else 1
            )
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("simulation", "order")
        ordering = ["timestamp"]

    def __str__(self) -> str:
        role_label = dict(RoleChoices.choices).get(self.role, self.role)
        return f"ChatLab Sim#{self.simulation.pk} Message #{self.order} ({role_label})"
