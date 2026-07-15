from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def _append_submission_reference(message, submission):
    if not submission:
        return message

    manuscript_reference = getattr(submission, 'manuscript_reference', None)
    if not manuscript_reference:
        return message

    reference_text = f'Reference: {manuscript_reference}'
    if reference_text in message:
        return message

    if message and message[-1] in '.!?':
        return f'{message} ({reference_text})'
    return f'{message} {reference_text}'


def notify_user(
    user,
    title,
    message,
    notification_type='system',
    send_email=True,
    submission=None,
):
    message = _append_submission_reference(message, submission)

    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
    )

    if send_email and user.email:
        send_mail(
            subject=title,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    return notification
