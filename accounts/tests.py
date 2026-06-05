from django.urls import reverse
from django.core import mail
from django.test import override_settings
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from journals.models import Classification
from user_notifications.models import Notification
from .models import Discipline, RoleChoice, User


class AccountMasterDataSoftDeleteTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email='manager@example.com',
            username='manager',
            full_name='Manager User',
            password='StrongPass123',
            is_editorial_manager=True,
        )
        self.author = User.objects.create_user(
            email='author@example.com',
            username='author',
            full_name='Author User',
            password='StrongPass123',
        )

    def test_role_choice_delete_only_deactivates_role_choice(self):
        role_choice = RoleChoice.objects.create(name='Professor')
        self.author.role_choice = role_choice
        self.author.save(update_fields=['role_choice'])

        self.client.force_authenticate(self.manager)
        response = self.client.delete(
            reverse('role-choice-detail', kwargs={'pk': role_choice.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        role_choice.refresh_from_db()
        self.author.refresh_from_db()

        self.assertFalse(role_choice.is_active)
        self.assertEqual(self.author.role_choice_id, role_choice.pk)

    def test_discipline_delete_only_deactivates_discipline(self):
        discipline = Discipline.objects.create(name='Computer Science')
        self.author.disciplines.add(discipline)

        self.client.force_authenticate(self.manager)
        response = self.client.delete(
            reverse('discipline-detail', kwargs={'pk': discipline.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        discipline.refresh_from_db()
        self.assertFalse(discipline.is_active)
        self.assertTrue(
            self.author.disciplines.filter(pk=discipline.pk).exists()
        )


class PromoteReviewerTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email='manager@example.com',
            username='manager',
            full_name='Manager User',
            password='StrongPass123',
            is_editorial_manager=True,
        )
        self.author = User.objects.create_user(
            email='author@example.com',
            username='author',
            full_name='Author User',
            password='StrongPass123',
        )
        self.classifications = [
            Classification.objects.create(name=f'Classification {index}')
            for index in range(1, 5)
        ]

    def test_manager_cannot_promote_author_without_classifications(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            reverse(
                'make_reviewer',
                kwargs={'user_id': self.author.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            'User must have at least 4 active classifications before '
            'becoming a reviewer.',
        )

    def test_manager_can_promote_author_with_four_classifications(self):
        self.author.classifications.set(self.classifications)

        self.client.force_authenticate(self.manager)
        response = self.client.post(
            reverse(
                'make_reviewer',
                kwargs={'user_id': self.author.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.author.refresh_from_db()
        self.assertTrue(self.author.is_reviewer)


class AccountClassificationSelectionTests(APITestCase):
    def setUp(self):
        self.classifications = [
            Classification.objects.create(name=f'Classification {index}')
            for index in range(1, 5)
        ]

    def test_register_author_does_not_require_classifications(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'new-author@example.com',
                'username': 'new-author',
                'full_name': 'New Author',
                'password': 'StrongPass123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='new-author@example.com')
        self.assertFalse(user.is_reviewer)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.classifications.count(), 0)

    def test_register_reviewer_requires_classifications(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'new-reviewer@example.com',
                'username': 'new-reviewer',
                'full_name': 'New Reviewer',
                'password': 'StrongPass123',
                'want_to_be_reviewer': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('classification_ids', response.data)

    def test_register_reviewer_requires_at_least_four_classifications(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'new-reviewer@example.com',
                'username': 'new-reviewer',
                'full_name': 'New Reviewer',
                'password': 'StrongPass123',
                'want_to_be_reviewer': True,
                'classification_ids': [
                    classification.id
                    for classification in self.classifications[:3]
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_reviewer_saves_four_classifications(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'new-reviewer@example.com',
                'username': 'new-reviewer',
                'full_name': 'New Reviewer',
                'password': 'StrongPass123',
                'want_to_be_reviewer': True,
                'classification_ids': [
                    classification.id
                    for classification in self.classifications
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='new-reviewer@example.com')
        self.assertTrue(user.is_reviewer)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.classifications.count(), 4)

    def test_profile_update_requires_classifications_when_becoming_reviewer(self):
        user = User.objects.create_user(
            email='author@example.com',
            username='author',
            full_name='Author User',
            password='StrongPass123',
        )

        self.client.force_authenticate(user)
        response = self.client.patch(
            reverse('profile'),
            {
                'want_to_be_reviewer': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('classification_ids', response.data)

    def test_profile_update_can_become_reviewer_with_four_classifications(self):
        user = User.objects.create_user(
            email='author@example.com',
            username='author',
            full_name='Author User',
            password='StrongPass123',
        )

        self.client.force_authenticate(user)
        response = self.client.patch(
            reverse('profile'),
            {
                'want_to_be_reviewer': True,
                'classification_ids': [
                    classification.id
                    for classification in self.classifications
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.is_reviewer)
        self.assertEqual(user.classifications.count(), 4)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_register_sends_verification_email_and_creates_notification(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'notified-author@example.com',
                'username': 'notified-author',
                'full_name': 'Notified Author',
                'password': 'StrongPass123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='notified-author@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify Your Email Address', mail.outbox[0].subject)
        self.assertTrue(
            Notification.objects.filter(
                user=user,
                title='Verify Your Email',
            ).exists()
        )

    def test_unverified_user_cannot_login(self):
        user = User.objects.create_user(
            email='unverified@example.com',
            username='unverified',
            full_name='Unverified User',
            password='StrongPass123',
        )

        response = self.client.post(
            reverse('login'),
            {
                'email': user.email,
                'password': 'StrongPass123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(
            'Please verify your email before logging in.',
            str(response.data),
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_verify_email_marks_user_verified_and_sends_welcome_email(self):
        user = User.objects.create_user(
            email='verify@example.com',
            username='verify',
            full_name='Verify User',
            password='StrongPass123',
            email_verification_otp=make_password('123456'),
            email_verification_otp_created_at=timezone.now(),
        )

        response = self.client.post(
            reverse('verify-email'),
            {
                'email': user.email,
                'otp': '123456',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertIsNone(user.email_verification_otp)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            'Welcome to Publication Manager',
        )
        self.assertTrue(
            Notification.objects.filter(
                user=user,
                title='Welcome to Publication Manager',
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_resend_verification_email_sends_new_otp_for_unverified_user(self):
        user = User.objects.create_user(
            email='resend@example.com',
            username='resend',
            full_name='Resend User',
            password='StrongPass123',
        )

        response = self.client.post(
            reverse('resend-verification-email'),
            {
                'email': user.email,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verification_otp)
        self.assertIsNotNone(user.email_verification_otp_created_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_check_email_shows_verify_action_for_unverified_user(self):
        user = User.objects.create_user(
            email='check@example.com',
            username='check',
            full_name='Check User',
            password='StrongPass123',
        )

        response = self.client.post(
            reverse('check_email'),
            {
                'email': user.email,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['action'], 'verify_email')
        self.assertFalse(response.data['user']['is_email_verified'])
