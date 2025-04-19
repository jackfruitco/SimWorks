"""
This module defines prompts and modifiers for simulating a standardized patient role player
in medical training scenarios. It includes various modifiers for chat styles, environments,
and specific conditions to enhance the realism of interactions. Use PromptTemplate to
dynamically construct composite prompts with chained modifier methods.
"""

from typing import Union
from accounts.models import UserRole
from core.utils import compute_fingerprint
from .models import Prompt
import hashlib


DEFAULT_PROMPT_BASE = (
    """
    You are simulating a standardized patient role player for medical training.

    Select a diagnosis and develop a corresponding clinical scenario script 
    using simple, everyday language that reflects the knowledge level of an
    average person.
    
    Avoid including narration, medical jargon, or any extraneous details that
    haven’t been explicitly requested. Adopt a natural texting style—using 
    informal language, common abbreviations—and maintain this tone 
    consistently throughout the conversation. Do not reveal your diagnosis or
    share clinical details beyond what a typical person would know. As a non-
    medical individual, refrain from attempting advanced tests or examinations
    unless explicitly instructed with detailed directions, and do not respond 
    as if you are medical staff.
    
    Generate only the first line of dialogue from the simulated patient 
    initiating contact, using a tone that is appropriate to the scenario, and
    remain in character at all times. If any off-topic or interrupting 
    requests arise, continue to respond solely as the simulated patient,
    addressing the conversation from within the current scenario without 
    repeating your role parameters.

    Do not exit the scenario.
    """
)

class UserRoleModifiers:
    def __init__(self, role=None):
        self.role = role

    def resource_list(self):
        if not self.role:
            return "None"
        qs = self.role.resources.all()
        return ", ".join(str(r) for r in qs) if qs.exists() else "None"

    def default(self):
        if not self.role:
            return "The person you are training has no specific role assigned.\n"
        return (
            f"The person you are training is a {self.role.title.title()}.\n"
            f"The diagnosis script should reflect training at that level.\n"
            f"Consider the following resources: {self.resource_list()}.\n"
        )

class Feedback:
    BASE = (
        """
        You are a simulation facilitator providing structured, constructive
        feedback to a trainee. Maintain a kind, respectful, and supportive
        tone—this is a developmental exercise, not an evaluation. Your goal is
        to help the user grow through clear, actionable insights. If the user
        is incorrect, ensure they understand what went wrong and how to 
        improve, without discouragement. Be direct, concise, and encouraging.
        
        Where applicable, provide evidence-based medicine, related screening 
        tools, and special tests or questionnaires the user could implement.
        """
    )

    ENDEX = (
        """
        Your feedback should aim to enhance the trainee's clinical reasoning,
        decision-making, and communication skills. Begin by clearly stating 
        the correct diagnosis from the simulation scenario and confirm whether
        the trainee correctly identified it. If they missed it, explain why 
        and guide them toward the correct diagnostic reasoning.
        
        Next, evaluate their recommended treatment plan. Indicate whether it
        was appropriate, and if not, describe what the correct plan would have 
        been and why.

        Offer practical suggestions to strengthen their diagnostic approach,
        including more effective or targeted questions they could have asked.
        Recommend specific resources (e.g., clinical guidelines, references,
        or reading materials) for further study if relevant.

        If the trainee did not achieve full credit in any performance area (
        diagnosis, treatment, communication), explain why in detail, and
        provide targeted advice for improving that score in future simulations.

        Your feedback should make the correct diagnosis and treatment plan 
        clear and unambiguous, even if the user did not reach them. It is not
        only acceptable—but required—to inform the trainee when their diagnosis
        or plan was incorrect, as long as it is done constructively.
        """
    )

    PAUSEX = (
        """
        The simulation is paused, and the user is asking for assistance—
        probably because they are stuck or lost. Provide recommendations on
        next steps that the user should take to advance their differential
        diagnosis process. Consider asking the user about potential diagnoses
        that could explain the presented symptom set, and suggest that they
        ask more history questions. Recommend using history-taking tools like
        SAMPLE, OPQRST, etc. if they haven't already. For this message only,
        you are the simulation facilitator. After this message, resume the role
        of the patient.
        """
    )

    AZIMUTH = (
        """
        For this message only, you are acting as the simulation facilitator
        responding to a user seeking confirmation that they are on the right
        track. You are not the patient and must not provide new scenario
        information.
        
        If the user appears to be asking irrelevant or misguided questions, 
        gently redirect them. Let them know they may be off course and suggest 
        a more productive line of questioning or an aspect of the patient’s 
        provided script they should revisit.
        
        Be supportive and constructive—your role is to coach, not to give
        answers. Encourage their clinical reasoning by guiding them toward 
        the correct approach rather than revealing it directly.
        """
    )

    @classmethod
    def default(cls):
        """Return the standard post-simulation feedback guidance."""
        return cls.BASE + cls.ENDEX


class ChatLabModifiers:
    """Modifiers for chat interactions in the simulated patient scenarios."""

    BASE = (
        """
        Adopt an SMS-like conversational tone from your very first message and
        maintain this informal style consistently throughout the conversation—
        without using slang or clinical language.

        Choose a diagnosis that a non-medical person might realistically text 
        about, and avoid conditions that clearly represent immediate 
        emergencies (such as massive trauma or a heart attack), which would not
        typically be communicated via text.
        """
    )

    @classmethod
    def default(cls):
        """Return the default chat style guidance for patient simulation."""
        return cls.BASE


class EnvironmentModifiers:
    """Modifiers for different environmental contexts in which the patient may be situated."""

    class Military:
        __slots__ = ()
        DEPLOYED_COMBAT = "You are deployed in a combat environment. "
        DEPLOYED_NONCOMBAT = "You are deployed in a noncombat environment. "
        GARRISON_ONDUTY = "You are in a garrison environment, on duty. "
        GARRISON_OFFDUTY = "You are in a garrison environment, off duty. "
        TRAINING = "You are at a training event in the field on a military base. "
        TRAINING_AUSTERE = (
            "You are at a training event not on a military installation, and "
            "are more than 3 hours from any medical care, including hospitals and EMS. "
        )

        @classmethod
        def default(cls):
            return cls.DEPLOYED_NONCOMBAT

    class EMS:
        CITY = "You are an EMS provider operating in a city."
        COUNTY = "You are an EMS provider operating in a rural county."
        AIR_MEDICAL = "You are a flight medic on an air medical transport."


class PromptModifiers:
    """Container for different types of prompt modifiers."""
    ChatLab = ChatLabModifiers
    Environ = EnvironmentModifiers
    Feedback = Feedback
    UserRole = UserRoleModifiers


class PromptTemplate:
    """
    Wrapper class that provides access to base prompt content and all related modifier groups.
    Supports a fluent interface to chain additional modifiers into the final prompt text.

    Example usage:
        prompt = PromptTemplate(role=some_role)
        prompt_text = prompt.default().with_chatlab().finalize()
        prompt_title = prompt.title
    """
    def __init__(self, role: Union[UserRole, int, None] = None, app_label: str = "ChatLab"):
        self.app_label = app_label
        self._cached_modifiers = None
        self._sections = []
        self._modifiers_used: list[str] = []        # used to generate prompt.title

        # Allow passing either a UserRole object, a role ID, or None
        # UserRole object should be passed to decrease DB hits
        if isinstance(role, int):
            try:
                self.role = UserRole.objects.get(id=role)
            except UserRole.DoesNotExist:
                self.role = None
        else:
            self.role = role

    @property
    def text(self) -> str:
        """Final assembled prompt text."""
        return "\n".join(section.strip() for section in self._sections if section)

    @property
    def title(self) -> str:
        base = f"{self.app_label} Prompt"
        parts = list(self._modifiers_used)

        # Include role title for uniqueness if present
        if self.role and self.role.title:
            parts.append(self.role.title)

        return f"{base} ({', '.join(parts)})" if parts else base

    @property
    def summary(self) -> str:
        """Return a structured summary of the prompt configuration."""
        role_title = self.role.title if self.role else "Unassigned"
        env_labels = [label for label in self._modifiers_used if label not in ("Base", "UserRole", "ChatLab", "Feedback", "PauseX", "Azimuth", "Summary")]
        return (
            f"Simulation Type: ChatLab\n"
            f"Training Role: {role_title}\n"
            f"Environment: {', '.join(env_labels) or 'Default'}\n"
            f"Included Modifiers: {', '.join(self._modifiers_used)}"
        )

    @property
    def base(self) -> str:
        return DEFAULT_PROMPT_BASE

    @property
    def modifiers(self):
        if not self._cached_modifiers:
            class Modifiers:
                ChatLab = ChatLabModifiers()
                Feedback = Feedback()
                Environ = EnvironmentModifiers()
                UserRole = UserRoleModifiers(role=self.role)
            self._cached_modifiers = Modifiers()
        return self._cached_modifiers

    def _add_modifier(self, content: str, label: str):
        if label not in self._modifiers_used:
            self._sections.append(content)
            self._modifiers_used.append(label)
        return self

    def add_modifier_label(self, label: str):
        """Add a modifier label manually for use in summaries."""
        if label and label not in self._modifiers_used:
            self._modifiers_used.append(label)

    def with_custom(self, label: str, content: str):
        return self._add_modifier(content, label)

    def default(self):
        self._add_modifier(self.base, "Base")
        if self.role:
            self._add_modifier(self.modifiers.UserRole.default(), "UserRole")
        return self

    def with_chatlab(self):
        return self._add_modifier(self.modifiers.ChatLab.default(), "ChatLab")

    def with_feedback(self):
        return self._add_modifier(self.modifiers.Feedback.default(), "Feedback")

    def with_pausex(self):
        return self._add_modifier(self.modifiers.Feedback.PAUSEX, "PauseX")

    def with_azimuth(self):
        return self._add_modifier(self.modifiers.Feedback.AZIMUTH, "Azimuth")

    def with_environment(self, modifier: str, label: str = None):
        return self._add_modifier(modifier, label or modifier.split()[0])

    def finalize(self) -> str:
        return "\n".join(section.strip() for section in self._sections if section)

    def clear(self):
        self._sections.clear()
        self._modifiers_used.clear()
        return self

modifiers = PromptModifiers()

def get_or_create_prompt(
    app_label: str = "ChatLab",
    role: Union[UserRole, int, None] = None,
    include_feedback: bool = False,
    environment: str = None,
    extra_modifiers: list[str] = None
) -> Prompt:
    """
    Build a Prompt instance using dynamic modifiers.
    - `app_label`: name of the app providing the simulation context
    - `role`: UserRole instance or ID
    - `include_feedback`: adds the feedback modifier (for facilitator guidance)
    - `environment`: optional string from EnvironmentModifiers (e.g., `TRAINING_AUSTERE`)
    - `extra_modifiers`: additional label strings to add to .summary for clarity
    """
    prompt = PromptTemplate(role=role, app_label=app_label).default()

    if app_label.lower() == "chatlab":
        prompt.with_chatlab()

    if include_feedback:
        prompt.with_feedback()

    if environment:
        env_string = getattr(PromptModifiers.Environ.Military, environment, None)
        if env_string:
            prompt.with_environment(env_string, label=environment)

    if extra_modifiers:
        for label in extra_modifiers:
            prompt.add_modifier_label(label)  # purely for summary visibility

    # Build fields
    title = prompt.title
    text = prompt.text
    summary = prompt.summary
    fingerprint = compute_fingerprint(title.strip(), text.strip())

    # Return Prompt instance with matching fingerprint if exists
    existing = Prompt.objects.filter(fingerprint=fingerprint).first()
    if existing:
        return existing

    # Check for Prompt instance with matching title, but not fingerprint
    # If existing, archive old instance and increment version on title
    prior = Prompt.objects.filter(title=title).first()
    if prior:
        prior.is_archived = True
        prior.save(update_fields=["is_archived"])
        base_title = title
        version = 2
        while Prompt.objects.filter(title=f"{base_title} v{version}").exists():
            version += 1
        title = f"{base_title} v{version}"

    return Prompt.objects.create(
        title=title,
        text=text,
        summary=summary,
        fingerprint=fingerprint,
        is_archived=False,
    )
