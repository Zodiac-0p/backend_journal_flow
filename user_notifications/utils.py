from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

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
    
    manuscript_reference = getattr(submission, 'manuscript_reference', None) if submission else None
    
    # Generate an action URL based on role if a submission is present
    action_url = None
    if submission:
        if getattr(user, 'is_editor', False) or getattr(user, 'is_editorial_manager', False) or getattr(user, 'is_super_admin', False) or getattr(user, 'is_superuser', False):
            action_url = f"http://localhost:5173/manager/assign-reviewers/{submission.id}"
        elif getattr(user, 'is_reviewer', False):
            action_url = f"http://localhost:5173/revision"
        else:
            action_url = f"http://localhost:5173/articles"

    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
    )

    if send_email and user.email:
        html_message = render_to_string('emails/notification.html', {
            'user_full_name': user.full_name or "User",
            'title': title,
            'message': message,
            'manuscript_reference': manuscript_reference,
            'action_url': action_url,
        })
        send_mail(
            subject=title,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )

    return notification
