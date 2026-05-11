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
class ProfileUpdateSerializer(serializers.ModelSerializer):
    want_to_be_reviewer = serializers.BooleanField(
        write_only=True,
        required=False
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
            'full_name',
            'phone',
            'affiliation',
            'organization',
            'job_title',
            'expertise',
            'want_to_be_reviewer',
            'role_choice_id',
            'discipline_ids',
        ]

    def update(self, instance, validated_data):
        want_to_be_reviewer = validated_data.pop('want_to_be_reviewer', None)
        role_choice_id = validated_data.pop('role_choice_id', None)
        discipline_ids = validated_data.pop('discipline_ids', None)

        # Update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Become reviewer immediately
        if want_to_be_reviewer is True:
            instance.is_reviewer = True

        # Update role choice
        if role_choice_id is not None:
            instance.role_choice = RoleChoice.objects.filter(
                id=role_choice_id,
                is_active=True
            ).first()

        instance.save()

        # Update disciplines
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