from django.urls import reverse
from django.core import mail
from django.test import override_settings
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


class AccountClassificationSelectionTests(APITestCase):
    def setUp(self):
        self.classifications = [
            Classification.objects.create(name=f'Classification {index}')
            for index in range(1, 5)
        ]

    def test_register_requires_at_least_four_classifications(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'new-author@example.com',
                'username': 'new-author',
                'full_name': 'New Author',
                'password': 'StrongPass123',
                'classification_ids': [
                    classification.id
                    for classification in self.classifications[:3]
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_saves_four_classifications(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'new-author@example.com',
                'username': 'new-author',
                'full_name': 'New Author',
                'password': 'StrongPass123',
                'classification_ids': [
                    classification.id
                    for classification in self.classifications
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='new-author@example.com')
        self.assertEqual(user.classifications.count(), 4)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_register_sends_email_and_creates_notification(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'notified-author@example.com',
                'username': 'notified-author',
                'full_name': 'Notified Author',
                'password': 'StrongPass123',
                'classification_ids': [
                    classification.id
                    for classification in self.classifications
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='notified-author@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            Notification.objects.filter(
                user=user,
                title='Welcome to Publication Manager',
            ).exists()
        )
