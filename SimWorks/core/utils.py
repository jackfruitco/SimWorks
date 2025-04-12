import os
import random

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from faker import Faker

fake = Faker()

# A unique sentinel to detect if a default value was provided.
_SENTINEL = object()

def check_env(var_name, default=_SENTINEL):
    """
    Retrieves the environment variable or returns the default if provided.
    Raises ImproperlyConfigured if the variable is not found and no default is provided.

    :param var_name: The name of the environment variable.
    :param default: The default value to return if the variable is not found.
                    If not provided, an error is raised.
    :return: The environment variable value or the default.
    """
    try:
        return os.environ[var_name]
    except KeyError:
        if default is not _SENTINEL:
            return default
        error_msg = f"{var_name} not found! Did you set the environment variable {var_name}?"
        raise ImproperlyConfigured(error_msg)

def generate_fake_name() -> str:
    return fake.name()


def randomize_display_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) < 2:
        return full_name  # fallback

    first, last = parts[0], parts[1]
    initials = f"{first[0]}{last[0]}"
    options = [
        full_name,
        f"{first} {last}",
        f"{first[0]}. {last}",
        f"{first} {last[0]}.",
        f"{first.lower()} {last.lower()}",
        f"{first.lower()} {last[0].lower()}",
        f"{initials}",
        f"{initials.upper()}",
        f"{first.capitalize()} {last[0].upper()}.",
        f"{first[0].upper()}.{last[0].upper()}.",
    ]
    return random.choice(options)


def get_user_initials(user) -> str:
    """
    Returns initials for a User object.
    - If first_name and last_name are set: returns first letters of each
    - If only username is set: returns first letter
    - If username is numeric: returns 'Unk'
    """

    User = get_user_model()
    if type(user) == str:
        try:
            user = User.objects.get(username=user)
        except User.DoesNotExist:
            raise Exception(f"Error! get_user_initials: Username {user} not found")

    if (
        hasattr(user, "first_name")
        and hasattr(user, "last_name")
        and user.first_name
        and user.last_name
    ):
        return f"{user.first_name[0]}{user.last_name[0]}".upper()
    elif hasattr(user, "username") and user.username and not user.username.isnumeric():
        return user.username[0].upper()
    return "Unk"
