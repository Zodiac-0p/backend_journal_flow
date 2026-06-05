from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from user_notifications.utils import notify_user
from .models import Submission, SubmissionStatus


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

    manuscript_label = (
        f'"{instance.title or instance}"'
        if (instance.title or instance)
        else 'your submission'
    )
    reference_suffix = (
        f' (Reference: {instance.manuscript_reference})'
        if instance.manuscript_reference
        else ''
    )

    if (
        previous_status == SubmissionStatus.DRAFT
        and instance.status == SubmissionStatus.UNDER_EDITOR_REVIEW
    ):
        title = 'Article Submitted Successfully'
        message = (
            f'Your article {manuscript_label}{reference_suffix} was submitted '
            'successfully and is now under editor review.'
        )
    else:
        status_label = instance.get_status_display()
        title = 'Submission Status Updated'
        message = (
            f'Your submission {manuscript_label}{reference_suffix} status '
            f'changed to {status_label}.'
        )

    notify_user(
        user=instance.author,
        title=title,
        message=message,
        notification_type='submission',
    )
