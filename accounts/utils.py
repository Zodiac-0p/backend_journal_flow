from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils import timezone
import secrets

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


def generate_email_verification_otp_for_user(user):
    otp = f'{secrets.randbelow(900000) + 100000}'
    user.email_verification_otp = make_password(otp)
    user.email_verification_otp_created_at = timezone.now()
    user.save(
        update_fields=[
            'email_verification_otp',
            'email_verification_otp_created_at',
        ]
    )
    return otp


def send_email_verification_email(user, otp):
    subject = 'Verify Your Email Address'
    message = f'''
Hello {user.full_name},

Welcome to Publication Manager.

Your email verification OTP is:

{otp}

This OTP will expire in {settings.EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES} minutes.

If you did not create this account, please ignore this email.

Publication Manager
'''

    notify_user(
        user=user,
        title='Verify Your Email',
        message=(
            'Please verify your email address using the OTP sent to your '
            'email inbox.'
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
