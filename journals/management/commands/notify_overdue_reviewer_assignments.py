from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from user_notifications.utils import notify_user
from journals.models import (
    ReviewerAssignmentStatus,
    SubmissionReviewerAssignment,
)


class Command(BaseCommand):
    help = (
        'Notify editors about pending reviewer assignments that have not '
        'received a response within the configured number of days.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Number of days to wait before notifying the editor.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show how many reminders would be sent without sending them.',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(days=days)

        assignments = SubmissionReviewerAssignment.objects.filter(
            is_active=True,
            status=ReviewerAssignmentStatus.PENDING,
            responded_at__isnull=True,
            reviewer_response_reminder_sent_at__isnull=True,
            assigned_at__lte=cutoff,
        ).select_related(
            'reviewer',
            'assigned_by',
            'submission',
            'submission__assigned_editor',
        )

        count = assignments.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'{count} overdue reviewer assignment reminder(s) would '
                    'be sent.'
                )
            )
            return

        sent_count = 0
        now = timezone.now()

        for assignment in assignments:
            editor = (
                assignment.submission.assigned_editor
                or assignment.assigned_by
            )

            if not editor:
                continue

            notify_user(
                user=editor,
                title='Reviewer Response Overdue',
                message=(
                    f'{assignment.reviewer.full_name} has not responded to '
                    'the review assignment for '
                    f'"{assignment.submission.title or assignment.submission}" '
                    f'within {days} days. Please assign another reviewer if '
                    'needed.'
                ),
                notification_type='review',
            )

            assignment.reviewer_response_reminder_sent_at = now
            assignment.save(
                update_fields=['reviewer_response_reminder_sent_at']
            )
            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Sent {sent_count} overdue reviewer assignment reminder(s).'
            )
        )
