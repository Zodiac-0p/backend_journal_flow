from django.utils import timezone
from rest_framework import serializers

from .models import (
    Subject,
    ArticleType,
    Classification,
    Submission,
    SubmissionVersion,
    SubmissionStatus,
)


# --------------------------------------------------
# Master Data Serializers
# --------------------------------------------------

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__'


class ArticleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleType
        fields = [
            'id',
            'name',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            # Only name is required
            'is_active': {'required': False},

        }

class ClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classification
        fields = '__all__'


# --------------------------------------------------
# Submission Version Serializer
# --------------------------------------------------

class SubmissionVersionSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.full_name',
        read_only=True
    )

    class Meta:
        model = SubmissionVersion
        fields = [
            'id',
            'version_number',
            'manuscript_file',
            'revision_notes',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
        ]
        read_only_fields = [
            'version_number',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
        ]


# --------------------------------------------------
# Submission Serializer
# --------------------------------------------------

class SubmissionSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(
        source='author.full_name',
        read_only=True
    )

    subject_name = serializers.CharField(
        source='subject.name',
        read_only=True
    )

    article_type_name = serializers.CharField(
        source='article_type.name',
        read_only=True
    )

    classifications_data = ClassificationSerializer(
        source='classifications',
        many=True,
        read_only=True
    )

    versions = SubmissionVersionSerializer(
        many=True,
        read_only=True
    )

    # Draft workflow status
    sections = serializers.ReadOnlyField()
    completed_sections = serializers.ReadOnlyField()
    total_sections = serializers.ReadOnlyField()
    is_ready_to_submit = serializers.ReadOnlyField()

    # Accept classification IDs from frontend
    discipline_ids = serializers.PrimaryKeyRelatedField(
        source='classifications',
        queryset=Classification.objects.filter(is_active=True),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Submission
        fields = '__all__'
        read_only_fields = [
            'author',
            'author_name',
            'subject_name',
            'article_type_name',
            'status',
            'submitted_at',
            'created_at',
            'updated_at',
            'versions',
            'sections',
            'completed_sections',
            'total_sections',
            'is_ready_to_submit',
        ]

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


# --------------------------------------------------
# Submit Draft Serializer
# --------------------------------------------------

class SubmitSubmissionSerializer(serializers.Serializer):
    def save(self, submission):
        if not submission.is_ready_to_submit:
            raise serializers.ValidationError(
                'Complete all required sections and accept the ethics policy.'
            )

        submission.status = SubmissionStatus.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save()
        return submission


# --------------------------------------------------
# Resubmit Serializer
# --------------------------------------------------

class ResubmitSerializer(serializers.Serializer):
    manuscript_file = serializers.FileField()
    revision_notes = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def save(self, submission, user):
        latest_version = submission.versions.first()
        next_version = (
            1 if not latest_version
            else latest_version.version_number + 1
        )

        SubmissionVersion.objects.create(
            submission=submission,
            version_number=next_version,
            manuscript_file=self.validated_data['manuscript_file'],
            revision_notes=self.validated_data.get(
                'revision_notes',
                ''
            ),
            uploaded_by=user,
        )

        submission.manuscript_file = self.validated_data['manuscript_file']
        submission.status = SubmissionStatus.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save()

        return submission