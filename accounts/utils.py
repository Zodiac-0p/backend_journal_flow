from django.core.mail import send_mail
from django.conf import settings


def send_reset_password_email(user, otp):
    subject = 'Reset Password OTP'

    message = f'''
Hello {user.full_name},

Your OTP for resetting password is:

{otp}

If you did not request this, please ignore this email.

Publication Manager
'''

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )