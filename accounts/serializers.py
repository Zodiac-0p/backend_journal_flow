from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from journals.models import Classification
from user_notifications.utils import notify_user
from .models import RoleChoice, Discipline
from .utils import (
    generate_email_verification_otp_for_user,
    send_email_verification_email,
)

User = get_user_model()

MIN_CLASSIFICATIONS_REQUIRED = 4


# ----------------------------------------------------------------------
# Role Choice Serializer
# ----------------------------------------------------------------------
class RoleChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleChoice
        fields = ['id', 'name', 'is_active']
        extra_kwargs = {
            'is_active': {'required': False},
        }


# ----------------------------------------------------------------------
# Discipline Serializer
# ----------------------------------------------------------------------
class DisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ['id', 'name', 'is_active']
        extra_kwargs = {
            'is_active': {'required': False},
        }


class UserClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classification
        fields = ['id', 'name', 'is_active']


def get_active_classifications(
    classification_ids,
    min_required=None,
):
    unique_ids = set(classification_ids)

    if (
        min_required is not None
        and len(unique_ids) < min_required
    ):
        raise serializers.ValidationError(
            f'Select at least {min_required} classifications.'
        )

    classifications = Classification.objects.filter(
        id__in=unique_ids,
        is_active=True,
    )

    if classifications.count() != len(unique_ids):
        raise serializers.ValidationError(
            'One or more selected classifications are invalid or inactive.'
        )

    return classifications


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

    classification_ids = serializers.ListField(
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
            'classification_ids',
        ]

    def validate(self, attrs):
        want_to_be_reviewer = attrs.get('want_to_be_reviewer', False)
        classification_ids = attrs.get('classification_ids')

        if want_to_be_reviewer and classification_ids is None:
            raise serializers.ValidationError({
                'classification_ids': [
                    (
                        'classification_ids is required when registering '
                        'as a reviewer.'
                    )
                ]
            })

        if classification_ids is not None:
            get_active_classifications(
                classification_ids,
                min_required=(
                    MIN_CLASSIFICATIONS_REQUIRED
                    if want_to_be_reviewer
                    else None
                ),
            )

        return attrs

    def create(self, validated_data):
        want_to_be_reviewer = validated_data.pop('want_to_be_reviewer', False)
        role_choice_id = validated_data.pop('role_choice_id', None)
        discipline_ids = validated_data.pop('discipline_ids', [])
        classification_ids = validated_data.pop('classification_ids', [])
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

        if classification_ids is not None:
            user.classifications.set(
                get_active_classifications(
                    classification_ids,
                    min_required=(
                        MIN_CLASSIFICATIONS_REQUIRED
                        if want_to_be_reviewer
                        else None
                    ),
                )
            )

        otp = generate_email_verification_otp_for_user(user)
        send_email_verification_email(user, otp)

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

    classification_ids = serializers.ListField(
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
            'classification_ids',
        ]

    def validate(self, attrs):
        wants_reviewer_now = attrs.get(
            'want_to_be_reviewer',
            self.instance.is_reviewer,
        )
        is_becoming_reviewer = (
            not self.instance.is_reviewer
            and wants_reviewer_now
        )
        classification_ids = attrs.get('classification_ids')

        if is_becoming_reviewer and classification_ids is None:
            raise serializers.ValidationError({
                'classification_ids': [
                    (
                        'classification_ids is required when changing '
                        'from author to reviewer.'
                    )
                ]
            })

        if classification_ids is not None:
            get_active_classifications(
                classification_ids,
                min_required=(
                    MIN_CLASSIFICATIONS_REQUIRED
                    if wants_reviewer_now
                    else None
                ),
            )

        return attrs

    def update(self, instance, validated_data):
        # Toggle reviewer status
        # True  -> becomes reviewer
        # False -> reverts to author (unless they have editor/admin roles)
        want_to_be_reviewer = validated_data.pop('want_to_be_reviewer', None)

        # Profile relationships
        role_choice_id = validated_data.pop('role_choice_id', None)
        discipline_ids = validated_data.pop('discipline_ids', None)
        classification_ids = validated_data.pop('classification_ids', None)

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

        if classification_ids is not None:
            instance.classifications.set(
                get_active_classifications(
                    classification_ids,
                    min_required=(
                        MIN_CLASSIFICATIONS_REQUIRED
                        if instance.is_reviewer
                        else None
                    ),
                )
            )

        return instance

# ----------------------------------------------------------------------
# User Serializer (Response)
# ----------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    primary_role = serializers.ReadOnlyField()
    role_choice = RoleChoiceSerializer(read_only=True)
    disciplines = DisciplineSerializer(many=True, read_only=True)
    classifications = UserClassificationSerializer(many=True, read_only=True)

    class Meta:
        model = User
        exclude = [
            'password',
            'groups',
            'user_permissions',
            'reset_password_otp',
            'reset_password_otp_created_at',
            'email_verification_otp',
            'email_verification_otp_created_at',
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
        if not self.user.is_email_verified:
            raise AuthenticationFailed(
                'Please verify your email before logging in.'
            )
        data['user'] = UserSerializer(self.user).data
        return data


# ----------------------------------------------------------------------
# Email Check Serializer
# ----------------------------------------------------------------------
class EmailCheckSerializer(serializers.Serializer):
    email = serializers.EmailField()


# ----------------------------------------------------------------------
# Password Reset Serializers
# ----------------------------------------------------------------------
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    otp = serializers.CharField(
        max_length=6,
    )

    new_password = serializers.CharField(
        min_length=8,
        write_only=True,
    )

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        email = attrs['email'].lower().strip()
        otp = attrs['otp']

        user = User.objects.filter(email__iexact=email).first()
        if (
            not user
            or not user.email_verification_otp
            or not user.email_verification_otp_created_at
        ):
            raise serializers.ValidationError({
                'otp': ['Invalid or expired OTP.']
            })

        expires_at = (
            user.email_verification_otp_created_at
            + timezone.timedelta(
                minutes=settings.EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES
            )
        )

        if timezone.now() > expires_at:
            raise serializers.ValidationError({
                'otp': ['Invalid or expired OTP.']
            })

        if not check_password(otp, user.email_verification_otp):
            raise serializers.ValidationError({
                'otp': ['Invalid or expired OTP.']
            })

        attrs['user'] = user
        return attrs


class ResendVerificationEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
