from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from user_notifications.utils import notify_user
from .models import Submission


@receiver(pre_save, sender=Submission)
def remember_previous_submission_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return

    instance._previous_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list('status', flat=True)
        .first()
    )


@receiver(post_save, sender=Submission)
def notify_author_on_submission_status_change(
    sender,
    instance,
    created,
    **kwargs
):
    previous_status = getattr(instance, '_previous_status', None)

    if created or previous_status == instance.status:
        return

    status_label = instance.get_status_display()

    notify_user(
        user=instance.author,
        title='Submission Status Updated',
        message=(
            f'Your submission "{instance.title or instance}" status '
            f'changed to {status_label}.'
        ),
        notification_type='submission',
    )
