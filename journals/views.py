from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Subject, ArticleType, Classification, Submission, SubmissionStatus
from .permissions import IsOwnerOrEditorialStaff, IsEditorialManagerOrSuperAdmin
from .serializers import (
    SubjectSerializer,
    ArticleTypeSerializer,
    ClassificationSerializer,
    SubmissionSerializer,
    SubmitSubmissionSerializer,
)


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.filter(is_active=True)
    serializer_class = SubjectSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsEditorialManagerOrSuperAdmin()]


class ArticleTypeViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleTypeSerializer

    def get_queryset(self):
        # Authors and reviewers see only active article types.
        if self.action in ['list', 'retrieve']:
            if (
                self.request.user.is_editorial_manager
                or self.request.user.is_super_admin
            ):
                return ArticleType.objects.all()
            return ArticleType.objects.filter(is_active=True)

        # Create/Update/Delete: only Editorial Manager and Super Admin
        return ArticleType.objects.all()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsEditorialManagerOrSuperAdmin()]


class ClassificationViewSet(SubjectViewSet):
    queryset = Classification.objects.filter(is_active=True)
    serializer_class = ClassificationSerializer


class SubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = SubmissionSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_super_admin or user.is_editorial_manager or user.is_editor:
            return Submission.objects.all().prefetch_related('classifications', 'versions')
        return Submission.objects.filter(author=user).prefetch_related('classifications', 'versions')

    def get_permissions(self):
        if self.action in ['list', 'create']:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsOwnerOrEditorialStaff()]

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        submission = self.get_object()
        serializer = SubmitSubmissionSerializer(data={})
        serializer.is_valid(raise_exception=True)
        serializer.save(submission)
        return Response(SubmissionSerializer(submission, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        submission = self.get_object()
        submission.status = SubmissionStatus.WITHDRAWN
        submission.save()
        return Response(SubmissionSerializer(submission, context={'request': request}).data)