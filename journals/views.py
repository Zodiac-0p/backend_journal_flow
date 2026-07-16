from rest_framework import status, viewsets, generics
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q

from user_notifications.utils import notify_user
from .models import (
    ArticleType,
    Classification,
    Submission,
    SubmissionStatus,
    ContributorRole,
    SubmissionAuthor,
    SubmissionFileType,
    SubmissionFile,
    SubmissionReviewerAssignment,
    SubmissionReviewerReport,
    ReviewerAssignmentStatus,
)
from .permissions import (
    IsOwnerOrEditorialStaff,
    IsEditorialManagerOrSuperAdmin,
    IsEditorOrAbove,
    IsReviewer,
)
from .serializers import (
    ArticleTypeSerializer,
    ClassificationSerializer,
    SubmissionSerializer,
    SubmitSubmissionSerializer,
    ResubmitSerializer,
    ContributorRoleSerializer,
    SubmissionAuthorSerializer,
    SubmissionFileTypeSerializer,
    SubmissionFileSerializer,
    ReviewerCandidateSerializer,
    AssignReviewerSerializer,
    SubmissionReviewerAssignmentSerializer,
    ReviewerAssignmentListSerializer,
    ReviewerAssignmentDetailSerializer,
    SubmissionReviewerReportSerializer,
    SubmissionReviewReportListSerializer,
    EditorDecisionSerializer,
    SendReviewCommentsToAuthorSerializer,
)

User = get_user_model()


def accessible_submissions_for(user):
    queryset = Submission.objects.select_related(
        'author',
        'article_type',
    )

    if (
        user.is_super_admin
        or user.is_editorial_manager
        or user.is_editor
    ):
        return queryset

    return queryset.filter(author=user)


def is_editor_or_above(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_editor
            or user.is_editorial_manager
            or user.is_super_admin
        )
    )


def eligible_reviewers_for(submission):
    classification_ids = submission.classifications.filter(
        is_active=True
    ).values_list('id', flat=True)
    assigned_reviewer_ids = submission.reviewer_assignments.filter(
        is_active=True
    ).values_list('reviewer_id', flat=True)

    return User.objects.filter(
        is_active=True,
        is_reviewer=True,
        classifications__id__in=classification_ids,
    ).exclude(
        id=submission.author_id,
    ).exclude(
        id__in=assigned_reviewer_ids,
    ).prefetch_related(
        'classifications',
    ).distinct().order_by(
        'full_name',
        'email',
    )


# ==================================================
# MASTER DATA VIEWSETS
# ==================================================


class SoftDeleteModelViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])


class ArticleTypeViewSet(SoftDeleteModelViewSet):
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


class ClassificationViewSet(SoftDeleteModelViewSet):
    serializer_class = ClassificationSerializer

    def get_queryset(self):
        user = self.request.user

        if (
            user.is_authenticated
            and (
                user.is_editorial_manager
                or user.is_super_admin
            )
        ):
            return Classification.objects.all()

        return Classification.objects.filter(
            is_active=True
        )

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]

        return [IsEditorialManagerOrSuperAdmin()]


class ContributorRoleViewSet(SoftDeleteModelViewSet):
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


class SubmissionFileTypeViewSet(SoftDeleteModelViewSet):
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
        return accessible_submissions_for(
            self.request.user
        ).prefetch_related(
            'classifications',
            'versions',
            'authors__contributor_roles',
            'submission_files__file_type',
        )

    def get_permissions(self):
        if self.action == 'published':
            return [AllowAny()]
            
        if self.action in ['list', 'create']:
            return [IsAuthenticated()]
            
        if self.action == 'publish':
            return [IsEditorialManagerOrSuperAdmin()]

        return [IsAuthenticated(), IsOwnerOrEditorialStaff()]

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        submission = self.get_object()

        serializer = SubmitSubmissionSerializer()
        missing_requirements = serializer.get_missing_requirements(
            submission
        )

        if missing_requirements:
            return Response(
                {
                    'detail': (
                        'Complete all required fields before final '
                        'submission.'
                    ),
                    'missing_requirements': missing_requirements,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(submission)

        return Response(
            SubmissionSerializer(
                submission,
                context={'request': request},
            ).data
        )

    @action(detail=False, methods=['get'])
    def published(self, request):
        submissions = Submission.objects.filter(
            status=SubmissionStatus.PUBLISHED
        ).prefetch_related(
            'classifications',
            'authors__contributor_roles',
            'submission_files__file_type',
        )
        serializer = self.get_serializer(submissions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        submission = self.get_object()
        
        if submission.status != SubmissionStatus.ACCEPTED:
            return Response(
                {'detail': 'Only accepted submissions can be published.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        submission.status = SubmissionStatus.PUBLISHED
        submission.save(update_fields=['status', 'updated_at'])

        return Response(
            SubmissionSerializer(
                submission,
                context={'request': request},
            ).data,
            status=status.HTTP_200_OK
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

        if submission.status not in [
            SubmissionStatus.MINOR_REVISION,
            SubmissionStatus.MAJOR_REVISION,
        ]:
            return Response(
                {
                    'detail': (
                        'Only submissions requiring minor or major revision '
                        'can be resubmitted.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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

    @action(
        detail=True,
        methods=['get'],
        url_path='selected-classifications',
    )
    def selected_classifications(self, request, pk=None):
        if not is_editor_or_above(request.user):
            return Response(
                {'detail': 'Only editor or above can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        submission = self.get_object()

        serializer = ClassificationSerializer(
            submission.classifications.filter(is_active=True),
            many=True,
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=['get'],
        url_path='eligible-reviewers',
    )
    def eligible_reviewers(self, request, pk=None):
        if not is_editor_or_above(request.user):
            return Response(
                {'detail': 'Only editor or above can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        submission = self.get_object()

        if submission.status not in [
            SubmissionStatus.SUBMITTED,
            SubmissionStatus.UNDER_EDITOR_REVIEW,
            SubmissionStatus.UNDER_PEER_REVIEW,
        ]:
            return Response(
                {
                    'detail': (
                        'Reviewers can only be listed for submitted, under '
                        'editor review, or under peer review submissions.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReviewerCandidateSerializer(
            eligible_reviewers_for(submission),
            many=True,
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=['post'],
        url_path='assign-reviewer',
    )
    def assign_reviewer(self, request, pk=None):
        if not is_editor_or_above(request.user):
            return Response(
                {'detail': 'Only editor or above can assign reviewers.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        submission = self.get_object()

        if submission.status not in [
            SubmissionStatus.SUBMITTED,
            SubmissionStatus.UNDER_EDITOR_REVIEW,
            SubmissionStatus.UNDER_PEER_REVIEW,
        ]:
            return Response(
                {
                    'detail': (
                        'Reviewers can only be assigned to submitted, under '
                        'editor review, or under peer review submissions.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AssignReviewerSerializer(
            data=request.data,
            context={
                'request': request,
                'submission': submission,
            },
        )
        serializer.is_valid(raise_exception=True)
        assignments = serializer.save()

        return Response(
            SubmissionReviewerAssignmentSerializer(
                assignments,
                many=True,
            ).data,
            status=status.HTTP_201_CREATED,
        )


# ==================================================
# SUBMISSION FILES
# ==================================================

class SubmissionFileListCreateView(generics.ListCreateAPIView):
    serializer_class = SubmissionFileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_submission(self):
        return get_object_or_404(
            accessible_submissions_for(self.request.user),
            id=self.kwargs['submission_id'],
        )

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
        return SubmissionFile.objects.filter(
            submission__in=accessible_submissions_for(self.request.user)
        ).select_related(
            'submission',
            'submission__author',
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
        return get_object_or_404(
            accessible_submissions_for(self.request.user),
            id=self.kwargs['submission_id'],
        )

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
        return SubmissionAuthor.objects.filter(
            submission__in=accessible_submissions_for(self.request.user)
        ).select_related(
            'submission',
            'submission__author',
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


# ==================================================
# REVIEWER ASSIGNMENT RESPONSES
# ==================================================

class ReviewerAssignmentResponseView(APIView):
    permission_classes = [IsAuthenticated]
    response_status = None

    def post(self, request, pk):
        assignment = get_object_or_404(
            SubmissionReviewerAssignment.objects.select_related(
                'submission',
                'submission__assigned_editor',
                'assigned_by',
                'reviewer',
            ),
            pk=pk,
            reviewer=request.user,
        )

        if assignment.status != ReviewerAssignmentStatus.PENDING:
            return Response(
                {'detail': 'This review assignment has already been answered.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.status = self.response_status
        assignment.responded_at = timezone.now()

        if self.response_status == ReviewerAssignmentStatus.REJECTED:
            assignment.is_active = False

        assignment.save(
            update_fields=[
                'status',
                'responded_at',
                'is_active',
            ]
        )

        editor = (
            assignment.submission.assigned_editor
            or assignment.assigned_by
        )
        if editor:
            action_label = assignment.get_status_display().lower()
            notify_user(
                user=editor,
                title='Reviewer Assignment Response',
                message=(
                    f'{assignment.reviewer.full_name} has {action_label} '
                    'the review assignment for '
                    f'"{assignment.submission.title or assignment.submission}".'
                ),
                notification_type='review',
                submission=assignment.submission,
            )

        return Response(
            SubmissionReviewerAssignmentSerializer(assignment).data,
            status=status.HTTP_200_OK,
        )


class AcceptReviewerAssignmentView(ReviewerAssignmentResponseView):
    response_status = ReviewerAssignmentStatus.ACCEPTED


class RejectReviewerAssignmentView(ReviewerAssignmentResponseView):
    response_status = ReviewerAssignmentStatus.REJECTED


class ReviewerAssignmentListView(generics.ListAPIView):
    serializer_class = ReviewerAssignmentListSerializer
    permission_classes = [IsReviewer]
    assignment_status = None

    def get_queryset(self):
        return SubmissionReviewerAssignment.objects.filter(
            reviewer=self.request.user,
            status=self.assignment_status,
            is_active=True,
        ).select_related(
            'submission',
            'submission__author',
            'submission__article_type',
            'assigned_by',
        ).order_by(
            '-assigned_at'
        )


class ReviewerPendingAssignmentListView(ReviewerAssignmentListView):
    assignment_status = ReviewerAssignmentStatus.PENDING


class ReviewerAcceptedAssignmentListView(ReviewerAssignmentListView):
    assignment_status = ReviewerAssignmentStatus.ACCEPTED


class ReviewerAssignmentDetailView(generics.RetrieveAPIView):
    serializer_class = ReviewerAssignmentDetailSerializer
    permission_classes = [IsReviewer]

    def get_queryset(self):
        return SubmissionReviewerAssignment.objects.filter(
            reviewer=self.request.user,
            is_active=True,
        ).select_related(
            'submission',
            'submission__author',
            'submission__article_type',
            'assigned_by',
            'reviewer',
            'review_report',
        ).prefetch_related(
            'reviewer__classifications',
        )


class ReviewerSubmitReportView(APIView):
    permission_classes = [IsReviewer]

    def post(self, request, pk):
        assignment = get_object_or_404(
            SubmissionReviewerAssignment.objects.select_related(
                'submission',
                'submission__assigned_editor',
                'assigned_by',
                'reviewer',
            ),
            pk=pk,
            reviewer=request.user,
            is_active=True,
        )

        if assignment.status != ReviewerAssignmentStatus.ACCEPTED:
            return Response(
                {
                    'detail': (
                        'Only accepted review assignments can submit a '
                        'review report.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = getattr(assignment, 'review_report', None)
        is_new_report = report is None
        was_transferred = (
            report.ready_to_transfer_to_editor
            if report else False
        )

        serializer = SubmissionReviewerReportSerializer(
            report,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        report = serializer.save(assignment=assignment)

        if report.ready_to_transfer_to_editor and not was_transferred:
            editor = assignment.submission.assigned_editor or assignment.assigned_by
            if editor:
                notify_user(
                    user=editor,
                    title='Reviewer Report Submitted',
                    message=(
                        f'{assignment.reviewer.full_name} has submitted the '
                        'review report for '
                        f'"{assignment.submission.title or assignment.submission}".'
                    ),
                    notification_type='review',
                    submission=assignment.submission,
                )

        response_status = (
            status.HTTP_201_CREATED
            if is_new_report
            else status.HTTP_200_OK
        )

        return Response(
            SubmissionReviewerReportSerializer(report).data,
            status=response_status,
        )


class SubmissionReviewReportListView(generics.ListAPIView):
    serializer_class = SubmissionReviewReportListSerializer
    permission_classes = [IsEditorOrAbove]

    def get_submission(self):
        return get_object_or_404(
            accessible_submissions_for(self.request.user),
            id=self.kwargs['submission_id'],
        )

    def get_queryset(self):
        submission = self.get_submission()
        return SubmissionReviewerReport.objects.filter(
            assignment__submission=submission,
            ready_to_transfer_to_editor=True,
        ).select_related(
            'assignment',
            'assignment__reviewer',
            'assignment__submission',
        ).prefetch_related(
            'assignment__reviewer__classifications',
        )


class EditorReviewReportListView(generics.ListAPIView):
    serializer_class = SubmissionReviewReportListSerializer
    permission_classes = [IsEditorOrAbove]

    def get_queryset(self):
        queryset = SubmissionReviewerReport.objects.filter(
            assignment__submission__in=accessible_submissions_for(
                self.request.user
            ),
            ready_to_transfer_to_editor=True,
        ).select_related(
            'assignment',
            'assignment__reviewer',
            'assignment__submission',
            'assignment__submission__author',
            'assignment__submission__article_type',
        ).prefetch_related(
            'assignment__reviewer__classifications',
        ).order_by(
            '-submitted_at',
            '-updated_at',
        )

        reviewer_id = self.request.query_params.get('reviewer_id')
        if reviewer_id:
            queryset = queryset.filter(
                assignment__reviewer_id=reviewer_id
            )

        submission_id = self.request.query_params.get('submission_id')
        if submission_id:
            queryset = queryset.filter(
                assignment__submission_id=submission_id
            )

        return queryset


class SubmissionEditorDecisionView(APIView):
    permission_classes = [IsEditorOrAbove]

    def post(self, request, submission_id):
        submission = get_object_or_404(
            accessible_submissions_for(request.user),
            id=submission_id,
        )

        serializer = EditorDecisionSerializer(
            data=request.data,
            context={'submission': submission},
        )
        serializer.is_valid(raise_exception=True)

        submission.status = serializer.validated_data['decision']
        submission.save(update_fields=['status', 'updated_at'])

        submission.reviewer_assignments.filter(
            is_active=True
        ).update(is_active=False)

        return Response(
            SubmissionSerializer(
                submission,
                context={'request': request},
            ).data,
            status=status.HTTP_200_OK,
        )


class SendReviewCommentsToAuthorView(APIView):
    permission_classes = [IsEditorOrAbove]

    def post(self, request, submission_id):
        submission = get_object_or_404(
            accessible_submissions_for(request.user),
            id=submission_id,
        )

        serializer = SendReviewCommentsToAuthorSerializer(
            data=request.data,
            context={'submission': submission},
        )
        serializer.is_valid(raise_exception=True)
        reports = serializer.context['reports']

        comment_sections = []
        for index, report in enumerate(reports, start=1):
            reviewer_name = report.assignment.reviewer.full_name
            comment_sections.append(
                (
                    f'Reviewer {index}: {reviewer_name}\n'
                    f'{report.reviewer_comments_to_author.strip()}'
                )
            )

        manuscript_title = submission.title or f'Submission #{submission.id}'
        reference_text = (
            f' ({submission.manuscript_reference})'
            if submission.manuscript_reference
            else ''
        )
        comments_body = '\n\n'.join(comment_sections)
        email_message = (
            f'Hello {submission.author.full_name},\n\n'
            f'The editor has shared completed reviewer comments for your '
            f'article "{manuscript_title}"{reference_text}.\n\n'
            f'{comments_body}\n\n'
            'Publication Manager'
        )

        send_mail(
            subject='Reviewer Comments for Your Submission',
            message=email_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[submission.author.email],
            fail_silently=False,
        )

        notify_user(
            user=submission.author,
            title='Reviewer Comments Shared',
            message=(
                'The editor has shared reviewer comments for your submission '
                f'"{manuscript_title}"{reference_text}.'
            ),
            notification_type='submission',
            send_email=False,
            submission=submission,
        )

        return Response(
            {
                'message': 'Reviewer comments sent to the author successfully.',
                'submission_id': submission.id,
                'sent_review_report_ids': [report.id for report in reports],
            },
            status=status.HTTP_200_OK,
        )
