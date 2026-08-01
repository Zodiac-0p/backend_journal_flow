from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    LoginView,
    ProfileView,
    PromoteToReviewerView,
    CheckEmailView,
    RoleChoiceViewSet,
    DisciplineViewSet,
    UserListView,
    CreateEditorAccountView,
    ForgotPasswordView,
    ResetPasswordView,
    ChangePasswordView,
    VerifyEmailView,
    ResendVerificationEmailView,
    CookieTokenRefreshView,
    LogoutView,
    SuperAdminLoginView,
    SuperAdminStatsView,
    SuperAdminUserListView,
    SuperAdminToggleManagerView,
    SuperAdminToggleUserActiveView,
    SuperAdminUserDetailView,
    SuperAdminCreateUserView,
    SuperAdminNotificationListView,
    SuperAdminNotificationDeleteView,
    SuperAdminReviewerAssignmentDeleteView,
    SuperAdminReviewReportDeleteView,
    SuperAdminSubmissionUpdateView,
    SuperAdminSubmissionAuthorUpdateView,
    SuperAdminSubmissionFileUpdateView,
    SuperAdminReviewerAssignmentUpdateView,
    SuperAdminReviewReportUpdateView,
    SuperAdminNotificationUpdateView,
)

# Router for Role Choices and Disciplines
router = DefaultRouter()
router.register('role-choices', RoleChoiceViewSet, basename='role-choice')
router.register('disciplines', DisciplineViewSet, basename='discipline')

urlpatterns = [
    # Authentication APIs
    path('check-email/', CheckEmailView.as_view(), name='check_email'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path(
        'resend-verification-email/',
        ResendVerificationEmailView.as_view(),
        name='resend-verification-email',
    ),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),

    # Profile APIs (GET and PATCH in same endpoint)
    path('profile/', ProfileView.as_view(), name='profile'),
    path('users/', UserListView.as_view(), name='user_list'),
    path(
        'users/create-editor/',
        CreateEditorAccountView.as_view(),
        name='create_editor_account',
    ),
    # Promote any existing user to reviewer
    path('users/<int:user_id>/make-reviewer/', PromoteToReviewerView.as_view(), name='make_reviewer'),

    path(
        'forgot-password/',
        ForgotPasswordView.as_view(),
        name='forgot-password',
    ),

    path(
        'reset-password/',
        ResetPasswordView.as_view(),
        name='reset-password',
    ),

    path(
        'change-password/',
        ChangePasswordView.as_view(),
        name='change-password',
    ),

    # ------------------------------------------------------------------
    # Super Admin URLs (non-obvious paths, not linked anywhere in UI)
    # ------------------------------------------------------------------
    path('sa-auth/', SuperAdminLoginView.as_view(), name='super_admin_login'),
    path('sa-stats/', SuperAdminStatsView.as_view(), name='super_admin_stats'),
    path('sa-users/', SuperAdminUserListView.as_view(), name='super_admin_users'),
    path('sa-users/create/', SuperAdminCreateUserView.as_view(), name='super_admin_create_user'),
    path('sa-users/<int:user_id>/toggle-manager/', SuperAdminToggleManagerView.as_view(), name='super_admin_toggle_manager'),
    path('sa-users/<int:user_id>/toggle-active/', SuperAdminToggleUserActiveView.as_view(), name='super_admin_toggle_active'),
    path('sa-users/<int:user_id>/detail/', SuperAdminUserDetailView.as_view(), name='super_admin_user_detail'),
    path('sa-notifications/', SuperAdminNotificationListView.as_view(), name='super_admin_notifications'),
    path('sa-notifications/<int:pk>/', SuperAdminNotificationDeleteView.as_view(), name='super_admin_notification_delete'),
    path('sa-reviewer-assignments/<int:pk>/', SuperAdminReviewerAssignmentDeleteView.as_view(), name='super_admin_reviewer_assignment_delete'),
    path('sa-review-reports/<int:pk>/', SuperAdminReviewReportDeleteView.as_view(), name='super_admin_review_report_delete'),
    path('sa-submissions/<int:pk>/edit/', SuperAdminSubmissionUpdateView.as_view(), name='super_admin_submission_update'),
    path('sa-submission-authors/<int:pk>/edit/', SuperAdminSubmissionAuthorUpdateView.as_view(), name='super_admin_submission_author_update'),
    path('sa-submission-files/<int:pk>/edit/', SuperAdminSubmissionFileUpdateView.as_view(), name='super_admin_submission_file_update'),
    path('sa-reviewer-assignments/<int:pk>/edit/', SuperAdminReviewerAssignmentUpdateView.as_view(), name='super_admin_reviewer_assignment_update'),
    path('sa-review-reports/<int:pk>/edit/', SuperAdminReviewReportUpdateView.as_view(), name='super_admin_review_report_update'),
    path('sa-notifications/<int:pk>/edit/', SuperAdminNotificationUpdateView.as_view(), name='super_admin_notification_update'),
]

# Append router-generated endpoints
urlpatterns += router.urls
