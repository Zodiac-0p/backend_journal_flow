from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ArticleTypeViewSet,
    ClassificationViewSet,
    SubmissionViewSet,
    ContributorRoleViewSet,
    SubmissionAuthorListCreateView,
    SubmissionAuthorDetailView,
    SubmissionFileTypeViewSet,
    SubmissionFileListCreateView,
    SubmissionFileDetailView,
    AcceptReviewerAssignmentView,
    RejectReviewerAssignmentView,
    ReviewerPendingAssignmentListView,
    ReviewerAcceptedAssignmentListView,
    ReviewerAssignmentDetailView,
    ReviewerSubmitReportView,
    SubmissionReviewReportListView,
    EditorReviewReportListView,
    SubmissionEditorDecisionView,
    SendReviewCommentsToAuthorView,
)

router = DefaultRouter()

# Master Data APIs
router.register('article-types', ArticleTypeViewSet, basename='article-type')
router.register('classifications', ClassificationViewSet, basename='classification')
router.register('contributor-roles', ContributorRoleViewSet, basename='contributor-role')
router.register(
    'submission-file-types',
    SubmissionFileTypeViewSet,
    basename='submission-file-type'
)

# Submission APIs
router.register('submissions', SubmissionViewSet, basename='submission')

urlpatterns = [
    # Step 4: Submission Authors
    path(
        'submissions/<int:submission_id>/authors/',
        SubmissionAuthorListCreateView.as_view(),
        name='submission-authors',
    ),
    path(
        'submission-authors/<int:pk>/',
        SubmissionAuthorDetailView.as_view(),
        name='submission-author-detail',
    ),
    path(
        'submissions/<int:submission_id>/files/',
        SubmissionFileListCreateView.as_view(),
        name='submission-files',
    ),
    path(
        'submission-files/<int:pk>/',
        SubmissionFileDetailView.as_view(),
        name='submission-file-detail',
    ),
    path(
        'reviewer-assignments/<int:pk>/accept/',
        AcceptReviewerAssignmentView.as_view(),
        name='reviewer-assignment-accept',
    ),
    path(
        'reviewer-assignments/pending/',
        ReviewerPendingAssignmentListView.as_view(),
        name='reviewer-assignment-pending-list',
    ),
    path(
        'reviewer-assignments/accepted/',
        ReviewerAcceptedAssignmentListView.as_view(),
        name='reviewer-assignment-accepted-list',
    ),
    path(
        'reviewer-assignments/<int:pk>/',
        ReviewerAssignmentDetailView.as_view(),
        name='reviewer-assignment-detail',
    ),
    path(
        'reviewer-assignments/<int:pk>/submit-report/',
        ReviewerSubmitReportView.as_view(),
        name='reviewer-assignment-submit-report',
    ),
    path(
        'reviewer-assignments/<int:pk>/reject/',
        RejectReviewerAssignmentView.as_view(),
        name='reviewer-assignment-reject',
    ),
    path(
        'submissions/<int:submission_id>/review-reports/',
        SubmissionReviewReportListView.as_view(),
        name='submission-review-reports',
    ),
    path(
        'review-reports/',
        EditorReviewReportListView.as_view(),
        name='editor-review-report-list',
    ),
    path(
        'submissions/<int:submission_id>/editor-decision/',
        SubmissionEditorDecisionView.as_view(),
        name='submission-editor-decision',
    ),
    path(
        'submissions/<int:submission_id>/send-review-comments/',
        SendReviewCommentsToAuthorView.as_view(),
        name='submission-send-review-comments',
    ),
]


# Include all router-generated URLs
urlpatterns += router.urls
