from django.urls import path

from .views import (
    NotificationListView,
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
    NotificationUnreadCountView,
)

urlpatterns = [
    path(
        '',
        NotificationListView.as_view(),
        name='notifications',
    ),

    path(
        'unread-count/',
        NotificationUnreadCountView.as_view(),
        name='unread-notifications-count',
    ),

    path(
        '<int:pk>/mark-read/',
        MarkNotificationReadView.as_view(),
        name='mark-notification-read',
    ),

    path(
        'mark-all-read/',
        MarkAllNotificationsReadView.as_view(),
        name='mark-all-notifications-read',
    ),
]