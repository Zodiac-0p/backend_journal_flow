from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    ProfileView,
    PromoteToReviewerView,
    CheckEmailView,
    RoleChoiceViewSet,
    DisciplineViewSet,
    UserListView,
)

# Router for Role Choices and Disciplines
router = DefaultRouter()
router.register('role-choices', RoleChoiceViewSet, basename='role-choice')
router.register('disciplines', DisciplineViewSet, basename='discipline')

urlpatterns = [
    # Authentication APIs
    path('check-email/', CheckEmailView.as_view(), name='check_email'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Profile APIs (GET and PATCH in same endpoint)
    path('profile/', ProfileView.as_view(), name='profile'),
    path('users/', UserListView.as_view(), name='user_list'),
    # Promote any existing user to reviewer
    path('users/<int:user_id>/make-reviewer/', PromoteToReviewerView.as_view(), name='make_reviewer'),
]

# Append router-generated endpoints
urlpatterns += router.urls