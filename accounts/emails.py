from datetime import date

from django.conf import settings
from django.core.mail import send_mail

from .models import User


def _get_recipient(collector: User) -> str | None:
    """Return the best email address for a collector, or None if not available."""
    email = (collector.email or "").strip()
    return email or None


def send_data_collector_welcome_email(collector: User, raw_password: str) -> None:
    """Send login credentials and daily target to a newly created data collector."""
    recipient = _get_recipient(collector)
    if not recipient:
        return

    identifier = collector.email or collector.phone_number or "your identifier"
    phone = collector.phone_number or "(not provided)"
    subject = "Your data collection account details"
    daily_target = collector.daily_target

    message = (
        f"Dear {collector.full_name},\n\n"
        "You have been added as a data collector on the survey platform.\n\n"
        "Login details:\n"
        f"- Username (email/phone): {identifier}\n"
        f"- Phone number: {phone}\n"
        f"- Password: {raw_password}\n"
        f"Your current daily target is: {daily_target} agents per day.\n\n"
        "Please sign in to the mobile app using these credentials and start collecting agents.\n\n"
        "Regards,\n"
        "Management"
    )

    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
        [recipient],
        fail_silently=True,
    )


def send_daily_target_updated_email(collector: User, old_target: int, new_target: int) -> None:
    """Notify a collector when their daily target is changed."""
    recipient = _get_recipient(collector)
    if not recipient:
        return

    subject = "Your daily target has been updated"
    message = (
        f"Dear {collector.full_name},\n\n"
        "Your daily target has been updated by your manager.\n\n"
        f"Previous target: {old_target} agents per day\n"
        f"New target: {new_target} agents per day\n\n"
        "Please plan your work accordingly.\n\n"
        "Regards,\n"
        "Management"
    )

    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
        [recipient],
        fail_silently=True,
    )


def send_daily_review_summary_email(
    collector: User,
    summary_date: date,
    approved_count: int,
    rejected_count: int,
) -> None:
    """Send a daily summary of approved/rejected agents for a collector."""
    recipient = _get_recipient(collector)
    if not recipient:
        return

    subject = f"Daily review summary for {summary_date.isoformat()}"
    message = (
        f"Dear {collector.full_name},\n\n"
        "Here is your summary for today's reviewed agents.\n\n"
        f"Date: {summary_date.isoformat()}\n"
        f"Approved agents: {approved_count}\n"
        f"Rejected agents: {rejected_count}\n\n"
        "Thank you for your work.\n\n"
        "Regards,\n"
        "Management"
    )

    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
        [recipient],
        fail_silently=True,
    )
