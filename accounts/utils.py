from django.core.mail import send_mail
from django.conf import settings

from user_notifications.utils import notify_user


def send_reset_password_email(user, otp):
    subject = 'Reset Password OTP'

    message = f'''
Hello {user.full_name},

Your OTP for resetting password is:

{otp}

If you did not request this, please ignore this email.

Publication Manager
'''

    notify_user(
        user=user,
        title='Password Reset Requested',
        message=(
            'A password reset OTP was requested for your Publication Manager '
            'account. If this was not you, please ignore the email.'
        ),
        notification_type='system',
        send_email=False,
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
