from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
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
# Promote any user to reviewer
# Allowed for Editorial Manager and Super Admin
# ----------------------------------------------------------------------
class PromoteToReviewerView(APIView):
    permission_classes = [IsEditorialManagerOrSuperAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if user.is_reviewer:
            return Response({
                "detail": f"{user.email} is already a reviewer."
            })

        user.is_reviewer = True
        user.save()

        return Response({
            "detail": f"{user.email} is now a reviewer."
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