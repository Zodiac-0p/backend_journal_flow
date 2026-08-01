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
    elif (
        previous_status in (
            SubmissionStatus.MINOR_REVISION,
            SubmissionStatus.MAJOR_REVISION,
        )
        and instance.status == SubmissionStatus.UNDER_EDITOR_REVIEW
    ):
        title = 'Revised Manuscript Submitted Successfully'
        message = (
            f'Your revised manuscript for {manuscript_label}{reference_suffix} '
            'has been resubmitted successfully and is now under editor review.'
        )
    elif instance.status == SubmissionStatus.UNDER_PEER_REVIEW:
        title = 'Article Assigned to Peer Reviewers'
        message = (
            f'Your manuscript {manuscript_label}{reference_suffix} has '
            'completed initial editorial screening and has been assigned to '
            'peer reviewers for formal evaluation.'
        )
    elif instance.status == SubmissionStatus.ACCEPTED:
        title = 'Article Accepted for Publication'
        message = (
            'Congratulations! We are pleased to inform you that your manuscript '
            f'{manuscript_label}{reference_suffix} has been ACCEPTED for '
            'publication in Publication Manager.'
        )
    elif instance.status == SubmissionStatus.REJECTED:
        title = 'Editorial Decision: Manuscript Not Accepted'
        message = (
            f'Thank you for submitting your manuscript {manuscript_label}'
            f'{reference_suffix} to Publication Manager. After careful '
            'consideration, we regret to inform you that your article has not '
            'been accepted for publication.'
        )
    elif instance.status in (
        SubmissionStatus.MINOR_REVISION,
        SubmissionStatus.MAJOR_REVISION,
    ):
        revision_type = (
            'Minor Revision'
            if instance.status == SubmissionStatus.MINOR_REVISION
            else 'Major Revision'
        )
        title = 'Revision Required for Your Submission'
        message = (
            f'An editorial decision of {revision_type} has been made for '
            f'your manuscript {manuscript_label}{reference_suffix}. Please '
            'review the feedback from the editorial team and submit your '
            'revised manuscript.'
        )
    elif instance.status == SubmissionStatus.PUBLISHED:
        title = 'Article Published Successfully'
        message = (
            'We are delighted to inform you that your manuscript '
            f'{manuscript_label}{reference_suffix} has been formally published.'
        )
    elif instance.status == SubmissionStatus.WITHDRAWN:
        title = 'Submission Withdrawn'
        message = (
            f'Your manuscript {manuscript_label}{reference_suffix} has '
            'been marked as withdrawn.'
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
        submission=instance,
    )
