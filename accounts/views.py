from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import RoleChoice, Discipline
from .permissions import IsEditorialManagerOrSuperAdmin
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ProfileUpdateSerializer,
    CustomTokenObtainPairSerializer,
    EmailCheckSerializer,
    RoleChoiceSerializer,
    DisciplineSerializer,
    UserListSerializer,
)

User = get_user_model()


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
            return Response({
                "exists": True,
                "action": "login",
                "message": "Email is already registered.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "primary_role": user.primary_role,
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


# ----------------------------------------------------------------------
# Login (JWT)
# ----------------------------------------------------------------------
class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


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
class RoleChoiceViewSet(viewsets.ModelViewSet):
    queryset = RoleChoice.objects.filter(is_active=True)
    serializer_class = RoleChoiceSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsEditorialManagerOrSuperAdmin()]


# ----------------------------------------------------------------------
# Disciplines (Multi-select categories)
# List: any authenticated user
# Create/Update/Delete: Editorial Manager or Super Admin
# ----------------------------------------------------------------------
class DisciplineViewSet(viewsets.ModelViewSet):
    queryset = Discipline.objects.filter(is_active=True)
    serializer_class = DisciplineSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsEditorialManagerOrSuperAdmin()]