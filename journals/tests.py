import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import (
    Submission,
    SubmissionAuthor,
    SubmissionFile,
    SubmissionFileType,
    SubmissionStatus,
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

    def test_resubmit_allows_minor_revision_status(self):
        submission = self.make_submission(SubmissionStatus.MINOR_REVISION)

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
