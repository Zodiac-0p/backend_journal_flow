from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import RoleChoice, Discipline

User = get_user_model()


# ----------------------------------------------------------------------
# Role Choice Serializer
# ----------------------------------------------------------------------
class RoleChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleChoice
        fields = ['id', 'name']


# ----------------------------------------------------------------------
# Discipline Serializer
# ----------------------------------------------------------------------
class DisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ['id', 'name']


# ----------------------------------------------------------------------
# Registration Serializer
# ----------------------------------------------------------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    want_to_be_reviewer = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False
    )

    role_choice_id = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True
    )

    discipline_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = User
        fields = [
            'email',
            'username',
            'full_name',
            'password',
            'phone',
            'affiliation',
            'organization',
            'job_title',
            'expertise',
            'want_to_be_reviewer',
            'role_choice_id',
            'discipline_ids',
        ]

    def create(self, validated_data):
        want_to_be_reviewer = validated_data.pop('want_to_be_reviewer', False)
        role_choice_id = validated_data.pop('role_choice_id', None)
        discipline_ids = validated_data.pop('discipline_ids', [])
        password = validated_data.pop('password')

        user = User(**validated_data)
        user.set_password(password)

        # Become reviewer immediately if selected
        if want_to_be_reviewer:
            user.is_reviewer = True

        # Set profile role
        if role_choice_id:
            user.role_choice = RoleChoice.objects.filter(
                id=role_choice_id,
                is_active=True
            ).first()

        user.save()

        # Set disciplines (multi-select)
        if discipline_ids:
            disciplines = Discipline.objects.filter(
                id__in=discipline_ids,
                is_active=True
            )
            user.disciplines.set(disciplines)

        return user


# ----------------------------------------------------------------------
# Profile Update Serializer
# ----------------------------------------------------------------------
# accounts/serializers.py

class ProfileUpdateSerializer(serializers.ModelSerializer):
    want_to_be_reviewer = serializers.BooleanField(write_only=True, required=False)
    role_choice_id = serializers.IntegerField(required=False, allow_null=True)
    discipline_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

    class Meta:
        model = User
        fields = [
            'full_name',
            'phone',
            'affiliation',
            'expertise',
            'job_title',
            'organization',
            'want_to_be_reviewer',
            'role_choice_id',
            'discipline_ids',
        ]

    def update(self, instance, validated_data):
        # Toggle reviewer status
        # True  -> becomes reviewer
        # False -> reverts to author (unless they have editor/admin roles)
        want_to_be_reviewer = validated_data.pop('want_to_be_reviewer', None)

        # Profile relationships
        role_choice_id = validated_data.pop('role_choice_id', None)
        discipline_ids = validated_data.pop('discipline_ids', None)

        # Update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Toggle reviewer status
        if want_to_be_reviewer is not None:
            instance.is_reviewer = want_to_be_reviewer

        # Update role choice
        if role_choice_id is not None:
            instance.role_choice = RoleChoice.objects.filter(
                id=role_choice_id,
                is_active=True
            ).first()

        # Save user
        instance.save()

        # Update disciplines (replace entire selection)
        if discipline_ids is not None:
            disciplines = Discipline.objects.filter(
                id__in=discipline_ids,
                is_active=True
            )
            instance.disciplines.set(disciplines)

        return instance

# ----------------------------------------------------------------------
# User Serializer (Response)
# ----------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    primary_role = serializers.ReadOnlyField()
    role_choice = RoleChoiceSerializer(read_only=True)
    disciplines = DisciplineSerializer(many=True, read_only=True)

    class Meta:
        model = User
        exclude = [
            'password',
            'groups',
            'user_permissions',
        ]

# ----------------------------------------------------------------------
# User List Serializer (Response)
# ----------------------------------------------------------------------
class UserListSerializer(serializers.ModelSerializer):
    primary_role = serializers.ReadOnlyField()
    role_choice_name = serializers.CharField(
        source='role_choice.name',
        read_only=True
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'username',
            'full_name',
            'primary_role',
            'is_reviewer',
            'is_editor',
            'is_editorial_manager',
            'is_super_admin',
            'job_title',
            'organization',
            'role_choice_name',
            'is_active',
            'created_at',
        ]
# ----------------------------------------------------------------------
# JWT Login Serializer
# ----------------------------------------------------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['full_name'] = user.full_name
        token['primary_role'] = user.primary_role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data


# ----------------------------------------------------------------------
# Email Check Serializer
# ----------------------------------------------------------------------
class EmailCheckSerializer(serializers.Serializer):
    email = serializers.EmailField()