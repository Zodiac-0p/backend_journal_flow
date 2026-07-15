from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.template.loader import render_to_string
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

    html_message = render_to_string('emails/reset_password.html', {
        'user_full_name': user.full_name or "User",
        'otp': otp,
    })

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True,
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

    html_message = render_to_string('emails/verify_email.html', {
        'user_full_name': user.full_name or "User",
        'otp': otp,
        'expiry_minutes': settings.EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES,
    })

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True,
    )


def generate_temporary_password(length=12):
    return get_random_string(
        length=length,
        allowed_chars=(
            'ABCDEFGHJKLMNPQRSTUVWXYZ'
            'abcdefghijkmnopqrstuvwxyz'
            '23456789'
            '!@#$%^&*'
        ),
    )


def send_editor_account_credentials_email(
    user,
    temporary_password,
    created_by,
):
    subject = 'Your Editor Account Has Been Created'
    message = f'''
Hello {user.full_name},

An editor account has been created for you in Publication Manager.

Created by:
{created_by.full_name} ({created_by.email})

Login credentials:
Email: {user.email}
Temporary Password: {temporary_password}

Please log in using these credentials.

Publication Manager
'''

    notify_user(
        user=user,
        title='Editor Account Created',
        message=(
            'Your editor account has been created by the editorial team. '
            'Please check your email for your login credentials.'
        ),
        notification_type='system',
        send_email=False,
    )

    html_message = render_to_string('emails/editor_credentials.html', {
        'user_full_name': user.full_name or "Editor",
        'created_by_name': created_by.full_name or "an Admin",
        'user_email': user.email,
        'temporary_password': temporary_password,
    })

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"SUCCESS: Email sent to {user.email}")
    except Exception as e:
        print("=======================================")
        print("EMAIL SENDING FAILED!")
        print(f"Error: {str(e)}")
        print("Please check your EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env")
        print("Make sure you have restarted the Django server after updating .env")
        print("=======================================")
