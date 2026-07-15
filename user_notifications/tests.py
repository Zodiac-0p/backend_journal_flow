from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()


class NotificationUnreadCountTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            username='user',
            password='Password123'
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            username='other',
            password='Password123'
        )
        # Create notifications for user
        Notification.objects.create(
            user=self.user,
            title='Test 1',
            message='Unread notification 1',
            is_read=False
        )
        Notification.objects.create(
            user=self.user,
            title='Test 2',
            message='Read notification',
            is_read=True
        )
        Notification.objects.create(
            user=self.user,
            title='Test 3',
            message='Unread notification 2',
            is_read=False
        )
        # Create notification for other user
        Notification.objects.create(
            user=self.other_user,
            title='Other Test',
            message='Other user unread',
            is_read=False
        )

    def test_get_unread_count_unauthenticated(self):
        url = reverse('unread-notifications-count')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_unread_count_authenticated(self):
        self.client.force_authenticate(self.user)
        url = reverse('unread-notifications-count')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 2)
