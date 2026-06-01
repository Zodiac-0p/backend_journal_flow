from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def notify_user(
    user,
    title,
    message,
    notification_type='system',
    send_email=True,
):
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
