#! /usr/bin/env python
"""Utils for Unpaywall"""
import os

from colrev.env.environment_manager import EnvironmentManager


UNPAYWALL_EMAIL_ENV_VAR = "UNPAYWALL_EMAIL"


def get_email() -> str:
    """Get user's name and email,

    if user have specified an email in registry, that will be returned
    otherwise it will return the email used in git
    """

    env_email = os.getenv(UNPAYWALL_EMAIL_ENV_VAR)
    if env_email:
        return env_email

    env_man = EnvironmentManager()
    _, email = env_man.get_name_mail_from_git()
    return email
