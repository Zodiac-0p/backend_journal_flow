from rest_framework.routers import DefaultRouter
from .views import (
    SubjectViewSet,
    ArticleTypeViewSet,
    ClassificationViewSet,
    SubmissionViewSet,
)

router = DefaultRouter()
router.register('subjects', SubjectViewSet, basename='subject')
router.register('article-types', ArticleTypeViewSet, basename='article-type')
router.register('classifications', ClassificationViewSet, basename='classification')
router.register('submissions', SubmissionViewSet, basename='submission')

urlpatterns = router.urls