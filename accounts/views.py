from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, DestroyAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
import secrets

from .utils import (
    send_reset_password_email,
    generate_email_verification_otp_for_user,
    send_email_verification_email,
)
from user_notifications.utils import notify_user
from .models import RoleChoice, Discipline
from .permissions import IsEditorialManagerOrSuperAdmin, IsEditorialStaff, IsSuperAdmin
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ProfileUpdateSerializer,
    CreateEditorAccountSerializer,
    CustomTokenObtainPairSerializer,
    EmailCheckSerializer,
    RoleChoiceSerializer,
    DisciplineSerializer,
    UserListSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    ChangePasswordSerializer,
    VerifyEmailSerializer,
    ResendVerificationEmailSerializer,
    MIN_CLASSIFICATIONS_REQUIRED,
)

User = get_user_model()


class SoftDeleteModelViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])


# ----------------------------------------------------------------------
# Check if email already exists
# ----------------------------------------------------------------------
class CheckEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower().strip()
        user = User.objects.filter(email=email).first()

        if user:
            action = 'login' if user.is_email_verified else 'verify_email'
            message = (
                'Email is already registered.'
                if user.is_email_verified
                else 'Email is registered but not verified yet.'
            )
            return Response({
                "exists": True,
                "action": action,
                "message": message,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "primary_role": user.primary_role,
                    "is_email_verified": user.is_email_verified,
                }
            })

        return Response({
            "exists": False,
            "action": "register",
            "message": "Email is not registered."
        })


# ----------------------------------------------------------------------
# Register new user
# ----------------------------------------------------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data = {
            'message': (
                'Account created successfully. Please verify your email '
                'using the OTP sent to your inbox before logging in.'
            ),
            'user': response.data,
        }
        return response


# ----------------------------------------------------------------------
# Login (JWT)
# ----------------------------------------------------------------------
class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            refresh_token = response.data.get('refresh')
            if refresh_token:
                response.set_cookie(
                    key='refresh_token',
                    value=refresh_token,
                    httponly=True,
                    secure=True,
                    samesite='None',
                )
                del response.data['refresh']
        return response


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response(
                {"detail": "No refresh token found in cookies."},
                status=status.HTTP_400_BAD_REQUEST
            )

        request.data['refresh'] = refresh_token

        try:
            response = super().post(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": getattr(e, 'detail', str(e))},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if response.status_code == 200 and 'refresh' in response.data:
            new_refresh = response.data.get('refresh')
            response.set_cookie(
                key='refresh_token',
                value=new_refresh,
                httponly=True,
                secure=True,
                samesite='None',
            )
            del response.data['refresh']

        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
        response.delete_cookie('refresh_token')
        return response


# ----------------------------------------------------------------------
# Get and update logged-in user profile
# ----------------------------------------------------------------------
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)

# ----------------------------------------------------------------------
#List all users with optional role filter
# Allowed for Editorial Manager and Super Admin
# ---------------------------------------------------------------------
class CreateEditorAccountView(generics.CreateAPIView):
    serializer_class = CreateEditorAccountSerializer
    permission_classes = [IsEditorialManagerOrSuperAdmin]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['created_by'] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        response_data = {
            'message': (
                'Editor account created successfully. Login credentials '
                'have been emailed to the editor.'
            ),
            'user': UserSerializer(user).data,
        }
        
        # Include temporary password in response for local development convenience
        if 'temporary_password' in serializer.context:
            response_data['temporary_password'] = serializer.context['temporary_password']

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )


class UserListView(ListAPIView):
    """
    List all users.
    Accessible by:
    - Editorial Manager
    - Super Admin

    Optional query parameter:
    ?role=author
    ?role=reviewer
    ?role=editor
    ?role=editorial_manager
    ?role=super_admin
    """
    serializer_class = UserListSerializer
    permission_classes = [IsEditorialStaff]

    def get_queryset(self):
        queryset = User.objects.select_related(
            'role_choice'
        ).prefetch_related(
            'disciplines'
        ).exclude(
            is_editorial_manager=True
        ).exclude(
            is_super_admin=True
        ).exclude(
            is_superuser=True
        ).order_by('-created_at')

        role = self.request.query_params.get('role')

        if role == 'author':
            queryset = queryset.filter(
                is_reviewer=False,
                is_editor=False,
                is_editorial_manager=False,
                is_super_admin=False,
            )

        elif role == 'reviewer':
            queryset = queryset.filter(is_reviewer=True)

        elif role == 'editor':
            queryset = queryset.filter(is_editor=True)

        elif role == 'editorial_manager':
            queryset = queryset.filter(is_editorial_manager=True)

        elif role == 'super_admin':
            queryset = queryset.filter(is_super_admin=True)

        return queryset
# ----------------------------------------------------------------------
# Promote any user to reviewer
# Allowed for Editorial Manager and Super Admin
# ----------------------------------------------------------------------
class PromoteToReviewerView(APIView):
    """
    Toggle reviewer status for any user.

    If the user is currently:
    - Author (is_reviewer = False) -> becomes Reviewer
    - Reviewer (is_reviewer = True) -> becomes Author

    Accessible by:
    - Editorial Manager
    - Super Admin
    """
    permission_classes = [IsEditorialManagerOrSuperAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.is_reviewer:
            active_classification_count = user.classifications.filter(
                is_active=True
            ).count()

            if active_classification_count < MIN_CLASSIFICATIONS_REQUIRED:
                return Response(
                    {
                        'detail': (
                            'User must have at least '
                            f'{MIN_CLASSIFICATIONS_REQUIRED} active '
                            'classifications before becoming a reviewer.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Toggle reviewer status
        user.is_reviewer = not user.is_reviewer
        user.save()

        notify_user(
            user=user,
            title='Role Changed',
            message='Your account role has been updated by an administrator. You will be logged out shortly to apply the new permissions.',
            notification_type='system',
            send_email=False,
        )

        return Response({
            "detail": (
                f"{user.email} is now a reviewer."
                if user.is_reviewer
                else f"{user.email} is now an author."
            ),
            "user_id": user.id,
            "email": user.email,
            "is_reviewer": user.is_reviewer,
            "primary_role": user.primary_role,
        })


# ----------------------------------------------------------------------
# Role Choices (Profile roles)
# List: any authenticated user
# Create/Update/Delete: Editorial Manager or Super Admin
# ----------------------------------------------------------------------
class RoleChoiceViewSet(SoftDeleteModelViewSet):
    serializer_class = RoleChoiceSerializer

    def get_queryset(self):
        if (
            self.request.user.is_editorial_manager
            or self.request.user.is_super_admin
        ):
            return RoleChoice.objects.all()

        return RoleChoice.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsEditorialManagerOrSuperAdmin()]


# ----------------------------------------------------------------------
# Disciplines (Multi-select categories)
# List: any authenticated user
# Create/Update/Delete: Editorial Manager or Super Admin
# ----------------------------------------------------------------------
class DisciplineViewSet(SoftDeleteModelViewSet):
    serializer_class = DisciplineSerializer

    def get_queryset(self):
        if (
            self.request.user.is_editorial_manager
            or self.request.user.is_super_admin
        ):
            return Discipline.objects.all()

        return Discipline.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsEditorialManagerOrSuperAdmin()]


# ----------------------------------------------------------------------
# Password reset
# ----------------------------------------------------------------------
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = ForgotPasswordSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower().strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if user:
            otp = f'{secrets.randbelow(900000) + 100000}'

            user.reset_password_otp = make_password(otp)
            user.reset_password_otp_created_at = timezone.now()

            user.save(
                update_fields=[
                    'reset_password_otp',
                    'reset_password_otp_created_at',
                ]
            )

            try:
                send_reset_password_email(user, otp)
            except Exception as e:
                print(f"Error sending reset password email: {e}")

        return Response({
            'message': (
                'If an account exists for this email, an OTP has been sent.'
            )
        })


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_confirm'

    def post(self, request):
        serializer = ResetPasswordSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower().strip()
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if (
            not user
            or not user.reset_password_otp
            or not user.reset_password_otp_created_at
        ):
            return Response(
                {
                    'error': 'Invalid or expired OTP.'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        expires_at = (
            user.reset_password_otp_created_at
            + timezone.timedelta(
                minutes=settings.PASSWORD_RESET_OTP_EXPIRY_MINUTES
            )
        )

        if timezone.now() > expires_at:
            user.reset_password_otp = None
            user.reset_password_otp_created_at = None
            user.save(
                update_fields=[
                    'reset_password_otp',
                    'reset_password_otp_created_at',
                ]
            )

            return Response(
                {
                    'error': 'Invalid or expired OTP.'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not check_password(otp, user.reset_password_otp):
            return Response(
                {
                    'error': 'Invalid or expired OTP.'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)

        user.reset_password_otp = None
        user.reset_password_otp_created_at = None

        user.save(
            update_fields=[
                'password',
                'reset_password_otp',
                'reset_password_otp_created_at',
            ]
        )

        notify_user(
            user=user,
            title='Password Reset Successful',
            message=(
                'Your Publication Manager password was reset successfully.'
            ),
            notification_type='system',
        )

        return Response({
            'message': 'Password reset successful.'
        })


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {"old_password": ["Wrong password."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        notify_user(
            user=user,
            title='Password Changed Successfully',
            message=(
                'Your Publication Manager password has been successfully changed.'
            ),
            notification_type='system',
        )

        return Response({
            'message': 'Password changed successfully.'
        })


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'email_verification'

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        user.is_email_verified = True
        user.email_verification_otp = None
        user.email_verification_otp_created_at = None
        user.save(
            update_fields=[
                'is_email_verified',
                'email_verification_otp',
                'email_verification_otp_created_at',
            ]
        )

        notify_user(
            user=user,
            title='Welcome to Publication Manager',
            message=(
                f'Hello {user.full_name}, your email has been verified and '
                'your Publication Manager account is ready to use.'
            ),
            notification_type='system',
        )

        return Response({
            'message': 'Email verified successfully. You can now log in.'
        })


class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'email_verification_resend'

    def post(self, request):
        serializer = ResendVerificationEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower().strip()
        user = User.objects.filter(email__iexact=email).first()

        if user and not user.is_email_verified:
            otp = generate_email_verification_otp_for_user(user)
            send_email_verification_email(user, otp)

        return Response({
            'message': (
                'If an unverified account exists for this email, a new '
                'verification OTP has been sent.'
            )
        })


# ----------------------------------------------------------------------
# Super Admin Login
# 3-factor: password  +  is_super_admin=True in DB  +  secret key
# URL is non-obvious (/accounts/sa-auth/) and heavily throttled (3/hour)
# ----------------------------------------------------------------------
class SuperAdminLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'super_admin_login'

    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        password = request.data.get('password', '')
        secret_key = request.data.get('secret_key', '')

        # Generic error — never reveal which field failed (security best practice)
        GENERIC_ERROR = Response(
            {'detail': 'Invalid credentials or access denied.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

        # Factor 1: email + password
        if not email or not password or not secret_key:
            return GENERIC_ERROR

        # Factor 2: secret key matches .env value
        expected_key = getattr(settings, 'SUPER_ADMIN_SECRET_KEY', '')
        if not expected_key or secret_key != expected_key:
            return GENERIC_ERROR

        # Factor 3: user must exist, be active, email verified, AND is_super_admin=True (live DB check)
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return GENERIC_ERROR

        if not user.check_password(password):
            return GENERIC_ERROR

        if not user.is_super_admin:
            return GENERIC_ERROR

        if not user.is_email_verified:
            return GENERIC_ERROR

        # All 3 factors passed — issue JWT token
        refresh = RefreshToken.for_user(user)
        refresh['email'] = user.email
        refresh['full_name'] = user.full_name
        refresh['primary_role'] = user.primary_role
        refresh['is_super_admin'] = True

        access_token = refresh.access_token

        return Response({
            'access': str(access_token),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# Super Admin — System Stats
# Returns counts of everything in the system for the dashboard
# Protected: only super admin can access
# ----------------------------------------------------------------------
class SuperAdminStatsView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from journals.models import Submission, SubmissionStatus

        total_users = User.objects.filter(is_active=True).count()
        total_authors = User.objects.filter(
            is_active=True,
            is_reviewer=False, is_editor=False,
            is_editorial_manager=False, is_super_admin=False,
        ).count()
        total_reviewers = User.objects.filter(is_active=True, is_reviewer=True).count()
        total_editors = User.objects.filter(is_active=True, is_editor=True).count()
        total_managers = User.objects.filter(is_active=True, is_editorial_manager=True).count()
        total_super_admins = User.objects.filter(is_active=True, is_super_admin=True).count()

        total_submissions = Submission.objects.count()
        draft_submissions = Submission.objects.filter(status=SubmissionStatus.DRAFT).count()
        submitted = Submission.objects.filter(status=SubmissionStatus.SUBMITTED).count()
        under_review = Submission.objects.filter(
            status__in=[SubmissionStatus.UNDER_EDITOR_REVIEW, SubmissionStatus.UNDER_PEER_REVIEW]
        ).count()
        accepted = Submission.objects.filter(status=SubmissionStatus.ACCEPTED).count()
        rejected = Submission.objects.filter(status=SubmissionStatus.REJECTED).count()
        published = Submission.objects.filter(status=SubmissionStatus.PUBLISHED).count()

        return Response({
            'users': {
                'total': total_users,
                'authors': total_authors,
                'reviewers': total_reviewers,
                'editors': total_editors,
                'managers': total_managers,
                'super_admins': total_super_admins,
            },
            'submissions': {
                'total': total_submissions,
                'draft': draft_submissions,
                'submitted': submitted,
                'under_review': under_review,
                'accepted': accepted,
                'rejected': rejected,
                'published': published,
            },
        })


# ----------------------------------------------------------------------
# Super Admin — Full User List (all roles, including managers & super admins)
# Protected: only super admin can access
# ----------------------------------------------------------------------
class SuperAdminUserListView(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = UserListSerializer

    def get_queryset(self):
        queryset = User.objects.select_related('role_choice').order_by('-created_at')
        role = self.request.query_params.get('role')
        if role == 'author':
            queryset = queryset.filter(
                is_reviewer=False, is_editor=False,
                is_editorial_manager=False, is_super_admin=False,
            )
        elif role == 'reviewer':
            queryset = queryset.filter(is_reviewer=True)
        elif role == 'editor':
            queryset = queryset.filter(is_editor=True)
        elif role == 'editorial_manager':
            queryset = queryset.filter(is_editorial_manager=True)
        elif role == 'super_admin':
            queryset = queryset.filter(is_super_admin=True)
        return queryset


# ----------------------------------------------------------------------
# Super Admin — Promote/Demote any user to/from Editorial Manager
# Protected: only super admin can access
# ----------------------------------------------------------------------
class SuperAdminToggleManagerView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_super_admin:
            return Response(
                {'detail': 'Cannot change the role of another Super Admin.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.is_editorial_manager = not user.is_editorial_manager
        # If promoted to manager, ensure editor flag is also set
        if user.is_editorial_manager:
            user.is_editor = True
        user.save()

        notify_user(
            user=user,
            title='Role Updated',
            message=(
                'Your account has been updated to Editorial Manager.'
                if user.is_editorial_manager
                else 'Your Editorial Manager access has been removed.'
            ),
            notification_type='system',
            send_email=False,
        )

        return Response({
            'detail': (
                f'{user.email} is now an Editorial Manager.'
                if user.is_editorial_manager
                else f'{user.email} is no longer an Editorial Manager.'
            ),
            'user': UserSerializer(user).data,
        })


# ----------------------------------------------------------------------
# Super Admin — Deactivate / Reactivate any user account
# Protected: only super admin can access
# ----------------------------------------------------------------------
class SuperAdminToggleUserActiveView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_super_admin:
            return Response(
                {'detail': 'Cannot deactivate another Super Admin account.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.is_active = not user.is_active
        user.save()

        return Response({
            'detail': (
                f'{user.email} account reactivated.'
                if user.is_active
                else f'{user.email} account deactivated.'
            ),
            'is_active': user.is_active,
        })


# ----------------------------------------------------------------------
# Super Admin — Get / Edit / Delete a single user
# GET    /api/accounts/sa-users/<id>/detail/
# PATCH  /api/accounts/sa-users/<id>/detail/
# DELETE /api/accounts/sa-users/<id>/detail/
# ----------------------------------------------------------------------
class SuperAdminUserDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def _get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    def get(self, request, user_id):
        user = self._get_user(user_id)
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserSerializer(user).data)

    def patch(self, request, user_id):
        user = self._get_user(user_id)
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Prevent editing another super admin
        if user.is_super_admin and user.id != request.user.id:
            return Response(
                {'detail': 'Cannot edit another Super Admin account.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Allowed editable fields via PATCH
        editable = [
            'full_name', 'phone', 'affiliation', 'organization',
            'country', 'job_title', 'expertise',
            'is_active', 'is_reviewer', 'is_editor',
            'is_editorial_manager', 'is_email_verified',
        ]
        for field in editable:
            if field in request.data:
                setattr(user, field, request.data[field])

        # Handle password change
        new_password = request.data.get('password')
        if new_password:
            user.set_password(new_password)

        user.save()
        return Response(UserSerializer(user).data)

    def delete(self, request, user_id):
        user = self._get_user(user_id)
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_super_admin:
            return Response(
                {'detail': 'Cannot delete a Super Admin account.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        email = user.email
        user.delete()
        return Response({'detail': f'{email} has been permanently deleted.'})


# ----------------------------------------------------------------------
# Super Admin — Create any role user
# POST /api/accounts/sa-users/create/
# ----------------------------------------------------------------------
class SuperAdminCreateUserView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        password = request.data.get('password', '')
        full_name = request.data.get('full_name', '')
        username = request.data.get('username', '') or email.split('@')[0]
        role = request.data.get('role', 'author')  # author|reviewer|editor|editorial_manager|super_admin

        if not email or not password or not full_name:
            return Response(
                {'detail': 'email, password, and full_name are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {'detail': 'A user with this email already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure unique username
        base = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{counter}'
            counter += 1

        user = User(
            email=email,
            username=username,
            full_name=full_name,
            phone=request.data.get('phone', ''),
            affiliation=request.data.get('affiliation', ''),
            organization=request.data.get('organization', ''),
            country=request.data.get('country', ''),
            job_title=request.data.get('job_title', ''),
            expertise=request.data.get('expertise', ''),
            is_email_verified=True,
            is_active=True,
        )
        user.set_password(password)

        # Assign role flags
        if role == 'reviewer':
            user.is_reviewer = True
        elif role == 'editor':
            user.is_editor = True
        elif role == 'editorial_manager':
            user.is_editorial_manager = True
            user.is_editor = True
        elif role == 'super_admin':
            user.is_super_admin = True

        user.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


# ----------------------------------------------------------------------
# Super Admin — List all notifications (across all users)
# GET /api/accounts/sa-notifications/
# ----------------------------------------------------------------------
class SuperAdminNotificationListView(ListAPIView):
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        from user_notifications.models import Notification
        return Notification.objects.select_related('user').order_by('-created_at')[:200]

    def get(self, request, *args, **kwargs):
        from user_notifications.models import Notification
        notifications = Notification.objects.select_related('user').order_by('-created_at')[:200]
        data = [
            {
                'id': n.id,
                'user_email': n.user.email if n.user else '—',
                'user_name': n.user.full_name if n.user else '—',
                'title': n.title,
                'message': n.message,
                'notification_type': n.notification_type,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
            }
            for n in notifications
        ]
        return Response(data)


# ----------------------------------------------------------------------
# Super Admin — Delete individual Notification, Reviewer Assignment, Review Report
# ----------------------------------------------------------------------
class SuperAdminNotificationDeleteView(DestroyAPIView):
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        from user_notifications.models import Notification
        return Notification.objects.all()


class SuperAdminReviewerAssignmentDeleteView(DestroyAPIView):
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        from journals.models import SubmissionReviewerAssignment
        return SubmissionReviewerAssignment.objects.all()


class SuperAdminReviewReportDeleteView(DestroyAPIView):
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        from journals.models import SubmissionReviewerReport
        return SubmissionReviewerReport.objects.all()


# ----------------------------------------------------------------------
# Super Admin — Full PATCH editing for Submissions, Authors, Files, Assignments, Reports, Notifications
# ----------------------------------------------------------------------
class SuperAdminSubmissionUpdateView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        from journals.models import Submission
        obj = Submission.objects.filter(pk=pk).first()
        if not obj:
            return Response({'detail': 'Not found.'}, status=404)
        for f in ['title', 'manuscript_reference', 'status']:
            if f in request.data:
                setattr(obj, f, request.data[f])
        obj.save()
        return Response({'id': obj.id, 'title': obj.title, 'status': obj.status})


class SuperAdminSubmissionAuthorUpdateView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        from journals.models import SubmissionAuthor
        obj = SubmissionAuthor.objects.filter(pk=pk).first()
        if not obj:
            return Response({'detail': 'Not found.'}, status=404)
        for f in ['first_name', 'last_name', 'email', 'institution']:
            if f in request.data:
                setattr(obj, f, request.data[f])
        obj.save()
        return Response({'id': obj.id, 'first_name': obj.first_name, 'last_name': obj.last_name})


class SuperAdminSubmissionFileUpdateView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        from journals.models import SubmissionFile
        obj = SubmissionFile.objects.filter(pk=pk).first()
        if not obj:
            return Response({'detail': 'Not found.'}, status=404)
        if 'original_filename' in request.data:
            obj.original_filename = request.data['original_filename']
            obj.save()
        return Response({'id': obj.id, 'original_filename': obj.original_filename})


class SuperAdminReviewerAssignmentUpdateView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        from journals.models import SubmissionReviewerAssignment
        obj = SubmissionReviewerAssignment.objects.filter(pk=pk).first()
        if not obj:
            return Response({'detail': 'Not found.'}, status=404)
        for f in ['status', 'is_active']:
            if f in request.data:
                setattr(obj, f, request.data[f])
        obj.save()
        return Response({'id': obj.id, 'status': obj.status})


class SuperAdminReviewReportUpdateView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        from journals.models import SubmissionReviewerReport
        obj = SubmissionReviewerReport.objects.filter(pk=pk).first()
        if not obj:
            return Response({'detail': 'Not found.'}, status=404)
        for f in ['recommendation', 'review_report_complete']:
            if f in request.data:
                setattr(obj, f, request.data[f])
        obj.save()
        return Response({'id': obj.id, 'recommendation': obj.recommendation})


class SuperAdminNotificationUpdateView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        from user_notifications.models import Notification
        obj = Notification.objects.filter(pk=pk).first()
        if not obj:
            return Response({'detail': 'Not found.'}, status=404)
        for f in ['title', 'message', 'is_read']:
            if f in request.data:
                setattr(obj, f, request.data[f])
        obj.save()
        return Response({'id': obj.id, 'title': obj.title})
