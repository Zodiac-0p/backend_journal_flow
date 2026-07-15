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
        'Send a reminder to reviewers 15 days after assignment if their '
        'review is still pending.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=15,
            help='Number of days to wait before sending a reminder.',
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

        # Retrieve assignments that are active, accepted, assigned >= 15 days ago,
        # have not received the report reminder yet, and do not have a completed report.
        assignments = SubmissionReviewerAssignment.objects.filter(
            is_active=True,
            status=ReviewerAssignmentStatus.ACCEPTED,
            reviewer_report_reminder_sent_at__isnull=True,
            assigned_at__lte=cutoff,
        ).select_related(
            'reviewer',
            'submission',
        )

        sent_count = 0
        now = timezone.now()

        for assignment in assignments:
            # Check if there is already a completed report
            report = getattr(assignment, 'review_report', None)
            if report and (
                report.review_report_complete
                or report.ready_to_transfer_to_editor
            ):
                continue

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f'Would send reminder to {assignment.reviewer.full_name} '
                        f'for "{assignment.submission.title or assignment.submission}"'
                    )
                )
                sent_count += 1
                continue

            notify_user(
                user=assignment.reviewer,
                title='Review Report Reminder',
                message=(
                    f'Dear {assignment.reviewer.full_name},\n\n'
                    f'This is a friendly reminder that you were assigned to review '
                    f'the manuscript "{assignment.submission.title or assignment.submission}" '
                    f'{days} days ago. Please submit your review report as soon as possible.'
                ),
                notification_type='review',
            )

            assignment.reviewer_report_reminder_sent_at = now
            assignment.save(
                update_fields=['reviewer_report_reminder_sent_at']
            )
            sent_count += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Dry run: {sent_count} reminder(s) would be sent.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully sent {sent_count} reviewer report reminder(s).'
                )
            )
