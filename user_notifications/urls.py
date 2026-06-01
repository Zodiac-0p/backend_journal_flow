from django.urls import path

from .views import (
    NotificationListView,
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
)

urlpatterns = [
    path(
        '',
        NotificationListView.as_view(),
        name='notifications',
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