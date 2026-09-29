import threading
import logging
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_mail_async(*args, **kwargs):
    """
    Sends an email in a background daemon thread so the main HTTP
    request is never blocked or frozen.
    """
    def _send():
        try:
            send_mail(*args, **kwargs)
            recipient = kwargs.get('recipient_list') or (args[3] if len(args) > 3 else 'unknown')
            print(f"Async email sent successfully to {recipient}")
        except Exception as exc:
            logger.error(f"Async email sending error: {exc}", exc_info=True)
            print(f"ASYNC EMAIL ERROR: {exc}")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
