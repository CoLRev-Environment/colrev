#! /usr/bin/env python
"""Utils for Unpaywall"""
from colrev.env.environment_manager import EnvironmentManager


UNPAYWALL_EMAIL_PATH = "packages.pdf_get.colrev.unpaywall.email"


def get_email() -> str:
    """Get user's name and email,

    if user have specified an email in registry, that will be returned
    otherwise it will return the email used in git
    """

    env_man = EnvironmentManager()
    env_mail = env_man.get_settings_by_key(UNPAYWALL_EMAIL_PATH)
    _, email = env_man.get_name_mail_from_git()
    email = env_mail or email
    return email
