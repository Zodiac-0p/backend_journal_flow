from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
import secrets

from .utils import (
    send_reset_password_email,
    generate_email_verification_otp_for_user,
    send_email_verification_email,
)
from user_notifications.utils import notify_user
from .models import RoleChoice, Discipline
from .permissions import IsEditorialManagerOrSuperAdmin
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
                    secure=False,  # Set to False for local development
                    samesite='Lax',
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
                secure=False,
                samesite='Lax',
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
    permission_classes = [IsEditorialManagerOrSuperAdmin]

    def get_queryset(self):
        queryset = User.objects.select_related(
            'role_choice'
        ).prefetch_related(
            'disciplines'
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

            send_reset_password_email(user, otp)

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
