from rest_framework import status, viewsets, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser

from .models import (
    Subject,
    ArticleType,
    Classification,
    Submission,
    SubmissionStatus,
    ContributorRole,
    SubmissionAuthor,
    SubmissionFileType,
    SubmissionFile,
)
from .permissions import (
    IsOwnerOrEditorialStaff,
    IsEditorialManagerOrSuperAdmin,
)
from .serializers import (
    SubjectSerializer,
    ArticleTypeSerializer,
    ClassificationSerializer,
    SubmissionSerializer,
    SubmitSubmissionSerializer,
    ResubmitSerializer,
    ContributorRoleSerializer,
    SubmissionAuthorSerializer,
    SubmissionFileTypeSerializer,
    SubmissionFileSerializer,
)


# ==================================================
# MASTER DATA VIEWSETS
# ==================================================

class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer

    def get_queryset(self):
        if (
            self.request.user.is_editorial_manager
            or self.request.user.is_super_admin
        ):
            return Subject.objects.all()

        return Subject.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]

        return [IsEditorialManagerOrSuperAdmin()]


class ArticleTypeViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleTypeSerializer

    def get_queryset(self):
        if (
            self.request.user.is_editorial_manager
            or self.request.user.is_super_admin
        ):
            return ArticleType.objects.all()

        return ArticleType.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]

        return [IsEditorialManagerOrSuperAdmin()]


class ClassificationViewSet(viewsets.ModelViewSet):
    serializer_class = ClassificationSerializer

    def get_queryset(self):
        if (
            self.request.user.is_editorial_manager
            or self.request.user.is_super_admin
        ):
            return Classification.objects.select_related('subject').all()

        return Classification.objects.select_related('subject').filter(
            is_active=True
        )

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
            
        return [IsEditorialManagerOrSuperAdmin()]


class ContributorRoleViewSet(viewsets.ModelViewSet):
    serializer_class = ContributorRoleSerializer

    def get_queryset(self):
        if (
            self.request.user.is_editorial_manager
            or self.request.user.is_super_admin
        ):
            return ContributorRole.objects.all()

        return ContributorRole.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]

        return [IsEditorialManagerOrSuperAdmin()]


class SubmissionFileTypeViewSet(viewsets.ModelViewSet):
    serializer_class = SubmissionFileTypeSerializer

    def get_queryset(self):
        if (
            self.request.user.is_editorial_manager
            or self.request.user.is_super_admin
        ):
            return SubmissionFileType.objects.all()

        return SubmissionFileType.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]

        return [IsEditorialManagerOrSuperAdmin()]


# ==================================================
# SUBMISSION VIEWSET
# ==================================================

class SubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = SubmissionSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Submission.objects.select_related(
            'author',
            'subject',
            'article_type',
        ).prefetch_related(
            'classifications',
            'versions',
            'authors__contributor_roles',
            'submission_files__file_type',
        )

        if (
            user.is_super_admin
            or user.is_editorial_manager
            or user.is_editor
        ):
            return queryset

        return queryset.filter(author=user)

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

        return Response(
            SubmissionSerializer(
                submission,
                context={'request': request},
            ).data
        )

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        submission = self.get_object()

        submission.status = SubmissionStatus.WITHDRAWN
        submission.save(update_fields=['status', 'updated_at'])

        return Response(
            SubmissionSerializer(
                submission,
                context={'request': request},
            ).data
        )

    @action(detail=True, methods=['post'])
    def resubmit(self, request, pk=None):
        submission = self.get_object()

        serializer = ResubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(submission=submission, user=request.user)

        return Response(
            SubmissionSerializer(
                submission,
                context={'request': request},
            ).data,
            status=status.HTTP_200_OK,
        )


# ==================================================
# SUBMISSION FILES
# ==================================================

class SubmissionFileListCreateView(generics.ListCreateAPIView):
    serializer_class = SubmissionFileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_submission(self):
        submission = Submission.objects.get(
            id=self.kwargs['submission_id']
        )

        if (
            submission.author != self.request.user
            and not self.request.user.is_editor
            and not self.request.user.is_editorial_manager
            and not self.request.user.is_super_admin
        ):
            raise PermissionDenied('Permission denied.')

        return submission

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['submission'] = self.get_submission()
        return context

    def get_queryset(self):
        submission = self.get_submission()
        return submission.submission_files.select_related(
            'file_type',
            'uploaded_by',
        )

    def perform_create(self, serializer):
        submission = self.get_submission()
        serializer.save(
            submission=submission,
            uploaded_by=self.request.user,
        )


class SubmissionFileDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = SubmissionFileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return SubmissionFile.objects.select_related(
            'submission',
            'file_type',
            'uploaded_by',
        )


# ==================================================
# SUBMISSION AUTHORS
# ==================================================

class SubmissionAuthorListCreateView(generics.ListCreateAPIView):
    serializer_class = SubmissionAuthorSerializer
    permission_classes = [IsAuthenticated]

    def get_submission(self):
        submission = Submission.objects.get(
            id=self.kwargs['submission_id']
        )

        if (
            submission.author != self.request.user
            and not self.request.user.is_editor
            and not self.request.user.is_editorial_manager
            and not self.request.user.is_super_admin
        ):
            raise PermissionDenied('Permission denied.')

        return submission

    def get_queryset(self):
        submission = self.get_submission()
        return submission.authors.prefetch_related(
            'contributor_roles'
        )

    def perform_create(self, serializer):
        submission = self.get_submission()

        if serializer.validated_data.get('is_corresponding_author'):
            submission.authors.update(
                is_corresponding_author=False
            )

        serializer.save(submission=submission)


class SubmissionAuthorDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = SubmissionAuthorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SubmissionAuthor.objects.select_related(
            'submission'
        ).prefetch_related(
            'contributor_roles'
        )

    def perform_update(self, serializer):
        author = self.get_object()

        if serializer.validated_data.get('is_corresponding_author'):
            author.submission.authors.exclude(
                id=author.id
            ).update(
                is_corresponding_author=False
            )

        serializer.save()
