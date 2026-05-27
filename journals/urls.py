from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    SubjectViewSet,
    ArticleTypeViewSet,
    ClassificationViewSet,
    SubmissionViewSet,
    ContributorRoleViewSet,
    SubmissionAuthorListCreateView,
    SubmissionAuthorDetailView,
    SubmissionFileTypeViewSet,
    SubmissionFileListCreateView,
    SubmissionFileDetailView,
)

router = DefaultRouter()

# Master Data APIs
router.register('subjects', SubjectViewSet, basename='subject')
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
]


# Include all router-generated URLs
urlpatterns += router.urls