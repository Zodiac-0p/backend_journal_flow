from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        )


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = Notification.objects.get(
            id=pk,
            user=request.user,
        )

        notification.is_read = True
        notification.save()

        return Response({
            'message': 'Notification marked as read.'
        })


class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).update(is_read=True)

        return Response({
            'message': 'All notifications marked as read.'
        })


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_notifications = Notification.objects.filter(
            user=request.user,
            is_read=False,
        )
        count = unread_notifications.count()
        
        role_changed_qs = unread_notifications.filter(title='Role Changed')
        role_changed = role_changed_qs.exists()
        
        # Auto-mark as read so it doesn't trigger again on relogin
        if role_changed:
            role_changed_qs.update(is_read=True)

        return Response({
            'unread_count': count,
            'role_changed': role_changed,
        })