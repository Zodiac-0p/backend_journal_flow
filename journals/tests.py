import shutil
import tempfile
from datetime import timedelta

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.db.models.signals import pre_save, post_save
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from user_notifications.models import Notification
from .signals import (
    remember_previous_submission_status,
    notify_author_on_submission_status_change,
)
from .models import (
    ArticleType,
    Submission,
    SubmissionAuthor,
    SubmissionFile,
    SubmissionFileType,
    SubmissionStatus,
    Classification,
    SubmissionReviewerAssignment,
    SubmissionReviewerReport,
    ReviewerAssignmentStatus,
)


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class SubmissionNestedObjectPermissionTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.owner = User.objects.create_user(
            email='owner@example.com',
            username='owner',
            full_name='Owner User',
            password='StrongPass123',
        )
        self.other_author = User.objects.create_user(
            email='other@example.com',
            username='other',
            full_name='Other User',
            password='StrongPass123',
        )
        self.editor = User.objects.create_user(
            email='editor@example.com',
            username='editor',
            full_name='Editor User',
            password='StrongPass123',
            is_editor=True,
        )

        self.submission = Submission.objects.create(
            author=self.owner,
            title='Private manuscript',
        )
        self.submission_author = SubmissionAuthor.objects.create(
            submission=self.submission,
            first_name='Jane',
            last_name='Doe',
            institution='ABC University',
            email='jane@example.com',
        )
        self.file_type = SubmissionFileType.objects.create(
            name='Manuscript',
            is_required=True,
            allow_multiple=False,
        )
        self.submission_file = SubmissionFile.objects.create(
            submission=self.submission,
            file_type=self.file_type,
            file=SimpleUploadedFile(
                'manuscript.txt',
                b'private manuscript',
                content_type='text/plain',
            ),
            uploaded_by=self.owner,
        )

    def test_other_author_cannot_access_submission_author_detail(self):
        self.client.force_authenticate(self.other_author)

        response = self.client.get(
            reverse(
                'submission-author-detail',
                kwargs={'pk': self.submission_author.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_author_cannot_access_submission_file_detail(self):
        self.client.force_authenticate(self.other_author)

        response = self.client.get(
            reverse(
                'submission-file-detail',
                kwargs={'pk': self.submission_file.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_can_access_submission_author_detail(self):
        self.client.force_authenticate(self.editor)

        response = self.client.get(
            reverse(
                'submission-author-detail',
                kwargs={'pk': self.submission_author.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_editor_can_access_submission_file_detail(self):
        self.client.force_authenticate(self.editor)

        response = self.client.get(
            reverse(
                'submission-file-detail',
                kwargs={'pk': self.submission_file.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class JournalMasterDataSoftDeleteTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.manager = User.objects.create_user(
            email='journal-manager@example.com',
            username='journal-manager',
            full_name='Journal Manager',
            password='StrongPass123',
            is_editorial_manager=True,
        )
        self.author = User.objects.create_user(
            email='journal-author@example.com',
            username='journal-author',
            full_name='Journal Author',
            password='StrongPass123',
        )
        self.submission = Submission.objects.create(
            author=self.author,
            title='Submission with file',
        )
        self.file_type = SubmissionFileType.objects.create(
            name='Master Manuscript',
            is_required=True,
            allow_multiple=False,
        )
        self.submission_file = SubmissionFile.objects.create(
            submission=self.submission,
            file_type=self.file_type,
            file=SimpleUploadedFile(
                'master-manuscript.txt',
                b'manuscript',
                content_type='text/plain',
            ),
            uploaded_by=self.author,
        )

    def test_submission_file_type_delete_only_deactivates_file_type(self):
        self.client.force_authenticate(self.manager)

        response = self.client.delete(
            reverse(
                'submission-file-type-detail',
                kwargs={'pk': self.file_type.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.file_type.refresh_from_db()

        self.assertFalse(self.file_type.is_active)
        self.assertTrue(
            SubmissionFile.objects.filter(pk=self.submission_file.pk).exists()
        )


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class SubmissionResubmitStatusTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.author = User.objects.create_user(
            email='revision-author@example.com',
            username='revision-author',
            full_name='Revision Author',
            password='StrongPass123',
        )

    def make_submission(self, status_value):
        return Submission.objects.create(
            author=self.author,
            title='Revision workflow manuscript',
            status=status_value,
        )

    def make_upload(self):
        return SimpleUploadedFile(
            'revised-manuscript.txt',
            b'revised manuscript',
            content_type='text/plain',
        )

    def test_resubmit_rejects_submission_not_in_revision_status(self):
        submission = self.make_submission(SubmissionStatus.SUBMITTED)

        self.client.force_authenticate(self.author)
        response = self.client.post(
            reverse('submission-resubmit', kwargs={'pk': submission.pk}),
            {
                'manuscript_file': self.make_upload(),
                'revision_notes': 'Updated manuscript.',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(submission.versions.count(), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_resubmit_allows_minor_revision_status_and_notifies_editor(self):
        submission = self.make_submission(SubmissionStatus.MINOR_REVISION)
        editor = User.objects.create_user(
            email='revision-editor@example.com',
            username='revision-editor',
            full_name='Revision Editor',
            password='StrongPass123',
            is_editor=True,
        )
        submission.assigned_editor = editor
        submission.manuscript_reference = 'ERX-117446'
        submission.save(update_fields=['assigned_editor', 'manuscript_reference'])

        self.client.force_authenticate(self.author)
        response = self.client.post(
            reverse('submission-resubmit', kwargs={'pk': submission.pk}),
            {
                'manuscript_file': self.make_upload(),
                'revision_notes': 'Updated manuscript.',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        submission.refresh_from_db()
        self.assertEqual(submission.status, SubmissionStatus.SUBMITTED)
        self.assertEqual(submission.versions.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        editor_email = next(
            email
            for email in mail.outbox
            if editor.email in email.to
        )
        self.assertIn(submission.title, editor_email.body)
        self.assertIn(submission.manuscript_reference, editor_email.body)
        self.assertTrue(
            Notification.objects.filter(
                user=editor,
                title='Revised Submission Received',
            ).exists()
        )

    def test_resubmit_allows_major_revision_status(self):
        submission = self.make_submission(SubmissionStatus.MAJOR_REVISION)

        self.client.force_authenticate(self.author)
        response = self.client.post(
            reverse('submission-resubmit', kwargs={'pk': submission.pk}),
            {
                'manuscript_file': self.make_upload(),
                'revision_notes': 'Updated manuscript.',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        submission.refresh_from_db()
        self.assertEqual(submission.status, SubmissionStatus.SUBMITTED)
        self.assertEqual(submission.versions.count(), 1)


class SubmissionClassificationSelectionTests(APITestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email='classification-author@example.com',
            username='classification-author',
            full_name='Classification Author',
            password='StrongPass123',
        )
        self.submission = Submission.objects.create(
            author=self.author,
            title='Classification manuscript',
        )
        self.classifications = [
            Classification.objects.create(name=f'Journal Classification {index}')
            for index in range(1, 5)
        ]

    def test_submission_update_requires_at_least_four_classifications(self):
        self.client.force_authenticate(self.author)

        response = self.client.patch(
            reverse('submission-detail', kwargs={'pk': self.submission.pk}),
            {
                'classification_ids': [
                    classification.id
                    for classification in self.classifications[:3]
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submission_update_accepts_four_classifications(self):
        self.client.force_authenticate(self.author)

        response = self.client.patch(
            reverse('submission-detail', kwargs={'pk': self.submission.pk}),
            {
                'classification_ids': [
                    classification.id
                    for classification in self.classifications
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.classifications.count(), 4)
        self.assertTrue(self.submission.sections['classifications'])


class ClassificationPublicReadTests(APITestCase):
    def test_unauthenticated_user_can_list_active_classifications(self):
        Classification.objects.create(name='Visible Classification')
        Classification.objects.create(
            name='Inactive Classification',
            is_active=False,
        )

        response = self.client.get(reverse('classification-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Visible Classification')


class SubmissionEditorAutoAssignmentTests(APITestCase):
    def test_submit_returns_missing_requirements_for_incomplete_submission(self):
        author = User.objects.create_user(
            email='incomplete-submit-author@example.com',
            username='incomplete-submit-author',
            full_name='Incomplete Submit Author',
            password='StrongPass123',
        )
        editor = User.objects.create_user(
            email='available-editor@example.com',
            username='available-editor',
            full_name='Available Editor',
            password='StrongPass123',
            is_editor=True,
        )
        submission = Submission.objects.create(
            author=author,
            title='',
        )

        self.client.force_authenticate(author)
        response = self.client.post(
            reverse('submission-submit', kwargs={'pk': submission.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            'Complete all required fields before final submission.',
        )
        self.assertIn('missing_requirements', response.data)

        missing_requirements = response.data['missing_requirements']
        self.assertEqual(
            missing_requirements['article_type'],
            'Select an article type.',
        )
        self.assertEqual(
            missing_requirements['author_details'],
            'Add at least one author.',
        )
        self.assertEqual(
            missing_requirements['open_access'],
            'Select an open access option.',
        )
        self.assertEqual(
            missing_requirements['ethics_accepted'],
            'Accept the ethics policy before final submission.',
        )
        self.assertEqual(
            missing_requirements['title_abstract_keywords'][
                'missing_fields'
            ],
            ['title', 'abstract', 'keywords'],
        )
        self.assertEqual(
            missing_requirements['classifications']['selected_count'],
            0,
        )
        self.assertEqual(
            missing_requirements['classifications']['required_count'],
            4,
        )
        self.assertEqual(
            missing_requirements['additional_information'][
                'accepted_fields'
            ],
            [
                'funding_information',
                'conflict_of_interest',
                'suggested_reviewers',
                'additional_notes',
            ],
        )
        self.assertNotIn('submission_files', missing_requirements)
        self.assertEqual(editor.assigned_editor_submissions.count(), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_submit_assigns_least_loaded_editor_and_notifies_editor(self):
        author = User.objects.create_user(
            email='submit-author@example.com',
            username='submit-author',
            full_name='Submit Author',
            password='StrongPass123',
        )
        loaded_editor = User.objects.create_user(
            email='loaded-editor@example.com',
            username='loaded-editor',
            full_name='Loaded Editor',
            password='StrongPass123',
            is_editor=True,
        )
        least_loaded_editor = User.objects.create_user(
            email='least-loaded-editor@example.com',
            username='least-loaded-editor',
            full_name='Least Loaded Editor',
            password='StrongPass123',
            is_editor=True,
        )
        article_type = ArticleType.objects.create(name='Research Article')
        classifications = [
            Classification.objects.create(name=f'Submit Class {index}')
            for index in range(1, 5)
        ]
        submission = Submission.objects.create(
            author=author,
            article_type=article_type,
            title='Ready manuscript',
            abstract='Ready abstract',
            keywords='ready, manuscript',
            open_access=True,
            funding_information='No funding.',
            ethics_accepted=True,
        )
        submission.classifications.set(classifications)
        SubmissionAuthor.objects.create(
            submission=submission,
            first_name='Ready',
            last_name='Author',
            institution='ABC University',
            email='ready@example.com',
        )
        Submission.objects.create(
            author=author,
            assigned_editor=loaded_editor,
            title='Existing editor workload',
            status=SubmissionStatus.UNDER_EDITOR_REVIEW,
        )

        self.client.force_authenticate(author)
        response = self.client.post(
            reverse('submission-submit', kwargs={'pk': submission.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        submission.refresh_from_db()
        self.assertEqual(submission.assigned_editor, least_loaded_editor)
        self.assertIsNotNone(submission.manuscript_reference)
        self.assertTrue(
            submission.manuscript_reference.startswith('ERX-')
        )
        self.assertEqual(
            submission.status,
            SubmissionStatus.UNDER_EDITOR_REVIEW,
        )
        self.assertEqual(len(mail.outbox), 2)
        editor_email = next(
            email
            for email in mail.outbox
            if least_loaded_editor.email in email.to
        )
        author_email = next(
            email
            for email in mail.outbox
            if author.email in email.to
        )
        self.assertIn(submission.title, editor_email.body)
        self.assertIn(submission.manuscript_reference, editor_email.body)
        self.assertIn(submission.title, author_email.body)
        self.assertIn(submission.manuscript_reference, author_email.body)
        self.assertTrue(
            Notification.objects.filter(
                user=least_loaded_editor,
                title='New Submission Assigned',
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=author,
                title='Article Submitted Successfully',
            ).exists()
        )


class SubmissionReviewerAssignmentTests(APITestCase):
    def make_review_report_payload(self, ready_to_transfer=True):
        return {
            'review_report_complete': True,
            'ready_to_transfer_to_editor': ready_to_transfer,
            'recommendation': 'minor_revision',
            'reviewer_comments_to_author': (
                'The manuscript is promising but needs minor revisions.'
            ),
            'confidential_comments_to_editor': (
                'The methods are useful and the paper can move forward.'
            ),
            'paper_referee_confidence': 'confident',
            'referee_suitability_rating': '100',
            'paper_quality_rating': 'significant',
            'paper_value_rating': 'minor_modifications',
            'suitable_for_different_journal': False,
            'content_original_work': True,
            'content_well_organised': True,
            'content_abstract_adequate': True,
            'content_technically_sound': True,
            'content_practical_application': True,
            'content_references_adequate': True,
            'presentation_explains_clearly': True,
            'presentation_methods_included': True,
            'presentation_demonstrates_value': True,
            'presentation_language_clear': True,
            'manuscript_classification': 'paper',
        }

    def save_submission_without_status_notifications(self):
        pre_save.disconnect(
            remember_previous_submission_status,
            sender=Submission,
        )
        post_save.disconnect(
            notify_author_on_submission_status_change,
            sender=Submission,
        )
        try:
            self.submission.save(update_fields=['status'])
        finally:
            pre_save.connect(
                remember_previous_submission_status,
                sender=Submission,
            )
            post_save.connect(
                notify_author_on_submission_status_change,
                sender=Submission,
            )

    def setUp(self):
        self.author = User.objects.create_user(
            email='assignment-author@example.com',
            username='assignment-author',
            full_name='Assignment Author',
            password='StrongPass123',
        )
        self.editor = User.objects.create_user(
            email='assignment-editor@example.com',
            username='assignment-editor',
            full_name='Assignment Editor',
            password='StrongPass123',
            is_editor=True,
        )
        self.matching_reviewer = User.objects.create_user(
            email='matching-reviewer@example.com',
            username='matching-reviewer',
            full_name='Matching Reviewer',
            password='StrongPass123',
            is_reviewer=True,
        )
        self.second_matching_reviewer = User.objects.create_user(
            email='second-matching-reviewer@example.com',
            username='second-matching-reviewer',
            full_name='Second Matching Reviewer',
            password='StrongPass123',
            is_reviewer=True,
        )
        self.other_reviewer = User.objects.create_user(
            email='other-reviewer@example.com',
            username='other-reviewer',
            full_name='Other Reviewer',
            password='StrongPass123',
            is_reviewer=True,
        )
        self.classifications = [
            Classification.objects.create(name=f'Assignment Class {index}')
            for index in range(1, 5)
        ]
        self.other_classification = Classification.objects.create(
            name='Other Assignment Class'
        )
        self.matching_reviewer.classifications.set(
            self.classifications[:2]
        )
        self.second_matching_reviewer.classifications.set(
            self.classifications[2:]
        )
        self.other_reviewer.classifications.set(
            [self.other_classification]
        )
        self.submission = Submission.objects.create(
            author=self.author,
            title='Submitted manuscript',
            status=SubmissionStatus.SUBMITTED,
        )
        self.submission.classifications.set(self.classifications)

    def test_editor_can_list_submission_selected_classifications(self):
        self.client.force_authenticate(self.editor)

        response = self.client.get(
            reverse(
                'submission-selected-classifications',
                kwargs={'pk': self.submission.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)

    def test_editor_can_list_only_matching_reviewers(self):
        self.client.force_authenticate(self.editor)

        response = self.client.get(
            reverse(
                'submission-eligible-reviewers',
                kwargs={'pk': self.submission.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        reviewer_ids = {reviewer['id'] for reviewer in response.data}
        self.assertEqual(
            reviewer_ids,
            {
                self.matching_reviewer.id,
                self.second_matching_reviewer.id,
            },
        )

    def test_author_cannot_list_eligible_reviewers(self):
        self.client.force_authenticate(self.author)

        response = self.client.get(
            reverse(
                'submission-eligible-reviewers',
                kwargs={'pk': self.submission.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_assign_matching_reviewer(self):
        self.client.force_authenticate(self.editor)

        response = self.client.post(
            reverse(
                'submission-assign-reviewer',
                kwargs={'pk': self.submission.pk},
            ),
            {
                'reviewer_id': self.matching_reviewer.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            SubmissionReviewerAssignment.objects.filter(
                submission=self.submission,
                reviewer=self.matching_reviewer,
            ).exists()
        )

        self.submission.refresh_from_db()
        self.assertEqual(
            self.submission.status,
            SubmissionStatus.UNDER_PEER_REVIEW,
        )

    def test_reviewer_can_list_pending_assigned_articles(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.PENDING,
            is_active=True,
        )

        self.client.force_authenticate(self.matching_reviewer)
        response = self.client.get(
            reverse('reviewer-assignment-pending-list')
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], assignment.id)
        self.assertEqual(
            response.data[0]['submission']['id'],
            self.submission.id,
        )
        self.assertEqual(
            response.data[0]['submission']['title'],
            self.submission.title,
        )

    def test_reviewer_can_list_accepted_articles(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )

        self.client.force_authenticate(self.matching_reviewer)
        response = self.client.get(
            reverse('reviewer-assignment-accepted-list')
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], assignment.id)
        self.assertEqual(
            response.data[0]['submission']['id'],
            self.submission.id,
        )

    def test_reviewer_can_get_assignment_detail(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )

        self.client.force_authenticate(self.matching_reviewer)
        response = self.client.get(
            reverse(
                'reviewer-assignment-detail',
                kwargs={'pk': assignment.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], assignment.id)
        self.assertEqual(
            response.data['submission']['id'],
            self.submission.id,
        )
        self.assertIsNone(response.data['review_report'])

    def test_non_reviewer_cannot_list_reviewer_assignments(self):
        self.client.force_authenticate(self.author)

        pending_response = self.client.get(
            reverse('reviewer-assignment-pending-list')
        )
        accepted_response = self.client.get(
            reverse('reviewer-assignment-accepted-list')
        )

        self.assertEqual(
            pending_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            accepted_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_reviewer_cannot_submit_report_for_pending_assignment(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.PENDING,
            is_active=True,
        )

        self.client.force_authenticate(self.matching_reviewer)
        response = self.client.post(
            reverse(
                'reviewer-assignment-submit-report',
                kwargs={'pk': assignment.pk},
            ),
            self.make_review_report_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_reviewer_can_submit_report_and_editor_is_notified(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )

        self.client.force_authenticate(self.matching_reviewer)
        response = self.client.post(
            reverse(
                'reviewer-assignment-submit-report',
                kwargs={'pk': assignment.pk},
            ),
            self.make_review_report_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        assignment.refresh_from_db()
        self.assertTrue(hasattr(assignment, 'review_report'))
        self.assertTrue(assignment.review_report.ready_to_transfer_to_editor)
        self.assertIsNotNone(assignment.review_report.submitted_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            Notification.objects.filter(
                user=self.editor,
                title='Reviewer Report Submitted',
            ).exists()
        )

    def test_editor_can_list_transferred_review_reports(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )
        SubmissionReviewerReport.objects.create(
            assignment=assignment,
            submitted_at=timezone.now(),
            **self.make_review_report_payload(),
        )

        self.client.force_authenticate(self.editor)
        response = self.client.get(
            reverse(
                'submission-review-reports',
                kwargs={'submission_id': self.submission.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['assignment_id'],
            assignment.id,
        )
        self.assertEqual(
            response.data[0]['submission']['id'],
            self.submission.id,
        )
        self.assertEqual(
            response.data[0]['reviewer']['id'],
            self.matching_reviewer.id,
        )

    def test_editor_can_list_all_transferred_review_reports(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )
        SubmissionReviewerReport.objects.create(
            assignment=assignment,
            submitted_at=timezone.now(),
            **self.make_review_report_payload(),
        )

        self.client.force_authenticate(self.editor)
        response = self.client.get(
            reverse('editor-review-report-list')
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['submission']['id'],
            self.submission.id,
        )
        self.assertEqual(
            response.data[0]['reviewer']['id'],
            self.matching_reviewer.id,
        )

    def test_editor_review_report_list_supports_reviewer_filter(self):
        matching_assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )
        second_assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.second_matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )
        SubmissionReviewerReport.objects.create(
            assignment=matching_assignment,
            submitted_at=timezone.now(),
            **self.make_review_report_payload(),
        )
        SubmissionReviewerReport.objects.create(
            assignment=second_assignment,
            submitted_at=timezone.now(),
            **self.make_review_report_payload(),
        )

        self.client.force_authenticate(self.editor)
        response = self.client.get(
            reverse('editor-review-report-list'),
            {'reviewer_id': self.second_matching_reviewer.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['reviewer']['id'],
            self.second_matching_reviewer.id,
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_editor_can_send_selected_review_comments_to_author(self):
        first_assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )
        second_assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.second_matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )
        first_report = SubmissionReviewerReport.objects.create(
            assignment=first_assignment,
            submitted_at=timezone.now(),
            **self.make_review_report_payload(),
        )
        second_report = SubmissionReviewerReport.objects.create(
            assignment=second_assignment,
            submitted_at=timezone.now(),
            **{
                **self.make_review_report_payload(),
                'reviewer_comments_to_author': (
                    'Please improve the discussion and cite recent work.'
                ),
            },
        )

        self.client.force_authenticate(self.editor)
        response = self.client.post(
            reverse(
                'submission-send-review-comments',
                kwargs={'submission_id': self.submission.pk},
            ),
            {
                'review_report_ids': [first_report.id, second_report.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn(first_report.reviewer_comments_to_author, email_body)
        self.assertIn(second_report.reviewer_comments_to_author, email_body)
        self.assertTrue(
            Notification.objects.filter(
                user=self.author,
                title='Reviewer Comments Shared',
            ).exists()
        )

    def test_editor_cannot_send_invalid_review_report_for_submission(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )
        report = SubmissionReviewerReport.objects.create(
            assignment=assignment,
            submitted_at=timezone.now(),
            ready_to_transfer_to_editor=False,
            review_report_complete=True,
            reviewer_comments_to_author='Draft comments only.',
        )

        self.client.force_authenticate(self.editor)
        response = self.client.post(
            reverse(
                'submission-send-review-comments',
                kwargs={'submission_id': self.submission.pk},
            ),
            {
                'review_report_ids': [report.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_editor_can_apply_decision_after_transferred_report(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
            responded_at=timezone.now(),
            is_active=True,
        )
        SubmissionReviewerReport.objects.create(
            assignment=assignment,
            submitted_at=timezone.now(),
            **self.make_review_report_payload(),
        )
        self.submission.status = SubmissionStatus.UNDER_PEER_REVIEW
        self.save_submission_without_status_notifications()

        self.client.force_authenticate(self.editor)
        response = self.client.post(
            reverse(
                'submission-editor-decision',
                kwargs={'submission_id': self.submission.pk},
            ),
            {
                'decision': SubmissionStatus.MINOR_REVISION,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.submission.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(
            self.submission.status,
            SubmissionStatus.MINOR_REVISION,
        )
        self.assertFalse(assignment.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            Notification.objects.filter(
                user=self.author,
                title='Submission Status Updated',
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_reviewer_assignment_notifies_reviewer_and_author(self):
        self.client.force_authenticate(self.editor)

        response = self.client.post(
            reverse(
                'submission-assign-reviewer',
                kwargs={'pk': self.submission.pk},
            ),
            {
                'reviewer_id': self.matching_reviewer.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(
            Notification.objects.filter(
                user=self.matching_reviewer,
                title='Reviewer Assignment',
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.author,
                title='Submission Status Updated',
            ).exists()
        )

    def test_editor_can_assign_multiple_matching_reviewers(self):
        self.client.force_authenticate(self.editor)

        response = self.client.post(
            reverse(
                'submission-assign-reviewer',
                kwargs={'pk': self.submission.pk},
            ),
            {
                'reviewer_ids': [
                    self.matching_reviewer.id,
                    self.second_matching_reviewer.id,
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            SubmissionReviewerAssignment.objects.filter(
                submission=self.submission,
                is_active=True,
            ).count(),
            2,
        )

        self.submission.refresh_from_db()
        self.assertEqual(
            self.submission.status,
            SubmissionStatus.UNDER_PEER_REVIEW,
        )

    def test_editor_can_add_reviewer_when_under_peer_review(self):
        SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
        )
        self.submission.status = SubmissionStatus.UNDER_PEER_REVIEW
        self.save_submission_without_status_notifications()

        self.client.force_authenticate(self.editor)
        response = self.client.post(
            reverse(
                'submission-assign-reviewer',
                kwargs={'pk': self.submission.pk},
            ),
            {
                'reviewer_id': self.second_matching_reviewer.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            SubmissionReviewerAssignment.objects.filter(
                submission=self.submission,
                is_active=True,
            ).count(),
            2,
        )

    def test_eligible_reviewers_excludes_already_assigned_reviewers(self):
        SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
        )
        self.submission.status = SubmissionStatus.UNDER_PEER_REVIEW
        self.save_submission_without_status_notifications()

        self.client.force_authenticate(self.editor)
        response = self.client.get(
            reverse(
                'submission-eligible-reviewers',
                kwargs={'pk': self.submission.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reviewer_ids = {reviewer['id'] for reviewer in response.data}
        self.assertNotIn(self.matching_reviewer.id, reviewer_ids)
        self.assertIn(self.second_matching_reviewer.id, reviewer_ids)

    def test_editor_cannot_assign_non_matching_reviewer(self):
        self.client.force_authenticate(self.editor)

        response = self.client.post(
            reverse(
                'submission-assign-reviewer',
                kwargs={'pk': self.submission.pk},
            ),
            {
                'reviewer_id': self.other_reviewer.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            SubmissionReviewerAssignment.objects.filter(
                submission=self.submission,
                reviewer=self.other_reviewer,
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_reviewer_can_accept_assignment_and_editor_is_notified(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
        )

        assignment.submission.manuscript_reference = 'ERX-123456'
        assignment.submission.save(update_fields=['manuscript_reference'])

        self.client.force_authenticate(self.matching_reviewer)
        response = self.client.post(
            reverse(
                'reviewer-assignment-accept',
                kwargs={'pk': assignment.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ReviewerAssignmentStatus.ACCEPTED,
        )
        self.assertIsNotNone(assignment.responded_at)
        self.assertTrue(assignment.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            Notification.objects.filter(
                user=self.editor,
                title='Reviewer Assignment Response',
            ).exists()
        )

        email_body = mail.outbox[0].body
        self.assertIn('ERX-123456', email_body)
        notification = Notification.objects.get(
            user=self.editor,
            title='Reviewer Assignment Response',
        )
        self.assertIn('ERX-123456', notification.message)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_reviewer_can_reject_assignment_and_editor_is_notified(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
        )

        self.client.force_authenticate(self.matching_reviewer)
        response = self.client.post(
            reverse(
                'reviewer-assignment-reject',
                kwargs={'pk': assignment.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ReviewerAssignmentStatus.REJECTED,
        )
        self.assertIsNotNone(assignment.responded_at)
        self.assertFalse(assignment.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            Notification.objects.filter(
                user=self.editor,
                title='Reviewer Assignment Response',
            ).exists()
        )

    def test_other_reviewer_cannot_answer_assignment(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.matching_reviewer,
            assigned_by=self.editor,
        )

        self.client.force_authenticate(self.second_matching_reviewer)
        response = self.client.post(
            reverse(
                'reviewer-assignment-accept',
                kwargs={'pk': assignment.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class OverdueReviewerAssignmentNotificationTests(APITestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email='overdue-author@example.com',
            username='overdue-author',
            full_name='Overdue Author',
            password='StrongPass123',
        )
        self.editor = User.objects.create_user(
            email='overdue-editor@example.com',
            username='overdue-editor',
            full_name='Overdue Editor',
            password='StrongPass123',
            is_editor=True,
        )
        self.reviewer = User.objects.create_user(
            email='overdue-reviewer@example.com',
            username='overdue-reviewer',
            full_name='Overdue Reviewer',
            password='StrongPass123',
            is_reviewer=True,
        )
        self.submission = Submission.objects.create(
            author=self.author,
            assigned_editor=self.editor,
            title='Overdue Review Manuscript',
            status=SubmissionStatus.UNDER_PEER_REVIEW,
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_command_notifies_editor_for_pending_assignment_after_three_days(self):
        self.submission.manuscript_reference = 'ERX-123456'
        self.submission.save(update_fields=['manuscript_reference'])

        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.reviewer,
            assigned_by=self.editor,
        )
        overdue_time = timezone.now() - timedelta(days=3, minutes=1)
        SubmissionReviewerAssignment.objects.filter(
            pk=assignment.pk
        ).update(assigned_at=overdue_time)

        call_command('notify_overdue_reviewer_assignments')

        assignment.refresh_from_db()
        self.assertIsNotNone(
            assignment.reviewer_response_reminder_sent_at
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            Notification.objects.filter(
                user=self.editor,
                title='Reviewer Response Overdue',
            ).exists()
        )

        email_body = mail.outbox[0].body
        self.assertIn('ERX-123456', email_body)
        notification = Notification.objects.get(
            user=self.editor,
            title='Reviewer Response Overdue',
        )
        self.assertIn('ERX-123456', notification.message)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_command_does_not_notify_recent_pending_assignment(self):
        SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.reviewer,
            assigned_by=self.editor,
        )

        call_command('notify_overdue_reviewer_assignments')

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            Notification.objects.filter(
                user=self.editor,
                title='Reviewer Response Overdue',
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_command_does_not_notify_same_assignment_twice(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.reviewer,
            assigned_by=self.editor,
        )
        overdue_time = timezone.now() - timedelta(days=3, minutes=1)
        SubmissionReviewerAssignment.objects.filter(
            pk=assignment.pk
        ).update(assigned_at=overdue_time)

        call_command('notify_overdue_reviewer_assignments')
        call_command('notify_overdue_reviewer_assignments')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            Notification.objects.filter(
                user=self.editor,
                title='Reviewer Response Overdue',
            ).count(),
            1,
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_command_notifies_reviewer_for_accepted_assignment_after_fifteen_days(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
        )
        overdue_time = timezone.now() - timedelta(days=15, minutes=1)
        SubmissionReviewerAssignment.objects.filter(
            pk=assignment.pk
        ).update(assigned_at=overdue_time)

        call_command('notify_overdue_reviewer_reports')

        assignment.refresh_from_db()
        self.assertIsNotNone(
            assignment.reviewer_report_reminder_sent_at
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            Notification.objects.filter(
                user=self.reviewer,
                title='Review Report Reminder',
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_command_does_not_notify_recent_accepted_assignment(self):
        SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
        )

        call_command('notify_overdue_reviewer_reports')

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            Notification.objects.filter(
                user=self.reviewer,
                title='Review Report Reminder',
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_command_does_not_notify_reviewer_twice(self):
        assignment = SubmissionReviewerAssignment.objects.create(
            submission=self.submission,
            reviewer=self.reviewer,
            assigned_by=self.editor,
            status=ReviewerAssignmentStatus.ACCEPTED,
        )
        overdue_time = timezone.now() - timedelta(days=15, minutes=1)
        SubmissionReviewerAssignment.objects.filter(
            pk=assignment.pk
        ).update(assigned_at=overdue_time)

        call_command('notify_overdue_reviewer_reports')
        call_command('notify_overdue_reviewer_reports')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            Notification.objects.filter(
                user=self.reviewer,
                title='Review Report Reminder',
            ).count(),
            1,
        )
