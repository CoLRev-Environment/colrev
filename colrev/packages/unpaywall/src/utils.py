"""Utils for Unpaywall"""
import colrev.review_manager

UNPAYWALL_EMAIL_PATH = "packages.pdf_get.colrev.unpaywall.email"


def get_email(review_manager: colrev.review_manager.ReviewManager) -> str:
    """Get user's name and email,

    if user have specified an email in registry, that will be returned
    otherwise it will return the email used in git
    """

    env_mail = review_manager.environment_manager.get_settings_by_key(
        UNPAYWALL_EMAIL_PATH
    )
    (
        _,
        email,
    ) = review_manager.environment_manager.get_name_mail_from_git()
    email = env_mail or email
    return email
