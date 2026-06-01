from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import serializers

from user_notifications.utils import notify_user
from .models import (
    ArticleType,
    Classification,
    Submission,
    SubmissionVersion,
    SubmissionStatus,
    ContributorRole,
    SubmissionAuthor,
    SubmissionFileType,
    SubmissionFile,
    SubmissionReviewerAssignment,
    ReviewerAssignmentStatus,
    MIN_CLASSIFICATIONS_REQUIRED,
)

User = get_user_model()


# --------------------------------------------------
# Master Data Serializers
# --------------------------------------------------

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
            'is_active': {'required': False},
        }


class SubmissionFileTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionFileType
        fields = [
            'id',
            'name',
            'is_required',
            'is_active',
            'allow_multiple',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'created_at',
            'updated_at',
        ]


class ClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classification
        fields = '__all__'


class ContributorRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContributorRole
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


# --------------------------------------------------
# Submission Author Serializers
# --------------------------------------------------

class SubmissionAuthorSerializer(serializers.ModelSerializer):
    contributor_role_ids = serializers.PrimaryKeyRelatedField(
        source='contributor_roles',
        queryset=ContributorRole.objects.filter(is_active=True),
        many=True,
        required=False,
        write_only=True,
    )

    contributor_roles = ContributorRoleSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = SubmissionAuthor
        fields = [
            'id',
            'submission',
            'first_name',
            'last_name',
            'institution',
            'email',
            'contributor_role_ids',
            'contributor_roles',
            'is_corresponding_author',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'submission',
            'created_at',
            'updated_at',
        ]


# --------------------------------------------------
# Submission File Serializers
# --------------------------------------------------

class SubmissionFileSerializer(serializers.ModelSerializer):
    file_type_name = serializers.CharField(
        source='file_type.name',
        read_only=True,
    )

    class Meta:
        model = SubmissionFile
        fields = [
            'id',
            'submission',
            'file_type',
            'file_type_name',
            'file',
            'original_filename',
            'file_size',
            'uploaded_by',
            'created_at',
        ]
        read_only_fields = [
            'submission',
            'original_filename',
            'file_size',
            'uploaded_by',
            'created_at',
        ]

    def validate(self, attrs):
        submission = self.context.get('submission')
        file_type = attrs.get('file_type')

        if submission and file_type and not file_type.allow_multiple:
            existing_files = SubmissionFile.objects.filter(
                submission=submission,
                file_type=file_type
            )

            if self.instance:
                existing_files = existing_files.exclude(
                    id=self.instance.id
                )

            if existing_files.exists():
                raise serializers.ValidationError({
                    'file_type': [
                        f'Only one file is allowed for {file_type.name}.'
                    ]
                })

        return attrs


# --------------------------------------------------
# Submission Version Serializer
# --------------------------------------------------

class SubmissionVersionSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.full_name',
        read_only=True,
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
# Reviewer Assignment Serializers
# --------------------------------------------------

class ReviewerCandidateSerializer(serializers.ModelSerializer):
    classifications = ClassificationSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'organization',
            'job_title',
            'expertise',
            'classifications',
        ]


class SubmissionReviewerAssignmentSerializer(serializers.ModelSerializer):
    reviewer = ReviewerCandidateSerializer(read_only=True)
    assigned_by_name = serializers.CharField(
        source='assigned_by.full_name',
        read_only=True,
    )

    class Meta:
        model = SubmissionReviewerAssignment
        fields = [
            'id',
            'submission',
            'reviewer',
            'assigned_by',
            'assigned_by_name',
            'assigned_at',
            'status',
            'responded_at',
            'reviewer_response_reminder_sent_at',
            'is_active',
        ]
        read_only_fields = [
            'submission',
            'reviewer',
            'assigned_by',
            'assigned_by_name',
            'assigned_at',
            'status',
            'responded_at',
            'reviewer_response_reminder_sent_at',
            'is_active',
        ]


class AssignReviewerSerializer(serializers.Serializer):
    reviewer_id = serializers.IntegerField(required=False)
    reviewer_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=False,
    )

    def validate(self, attrs):
        reviewer_id = attrs.get('reviewer_id')
        reviewer_ids = attrs.get('reviewer_ids')

        if reviewer_id is None and reviewer_ids is None:
            raise serializers.ValidationError(
                'Provide reviewer_id or reviewer_ids.'
            )

        if reviewer_id is not None and reviewer_ids is not None:
            raise serializers.ValidationError(
                'Provide either reviewer_id or reviewer_ids, not both.'
            )

        selected_ids = reviewer_ids if reviewer_ids is not None else [
            reviewer_id
        ]

        if len(set(selected_ids)) != len(selected_ids):
            raise serializers.ValidationError(
                'Reviewer IDs must be unique.'
            )

        reviewers = [
            self.get_valid_reviewer(reviewer_id)
            for reviewer_id in selected_ids
        ]
        self.context['reviewers'] = reviewers

        return attrs

    def get_valid_reviewer(self, value):
        submission = self.context['submission']

        try:
            reviewer = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('Reviewer not found.')

        if not reviewer.is_active or not reviewer.is_reviewer:
            raise serializers.ValidationError(
                'Selected user is not an active reviewer.'
            )

        if reviewer == submission.author:
            raise serializers.ValidationError(
                'Submission author cannot be assigned as reviewer.'
            )

        submission_classification_ids = set(
            submission.classifications.filter(
                is_active=True
            ).values_list('id', flat=True)
        )
        reviewer_classification_ids = set(
            reviewer.classifications.filter(
                is_active=True
            ).values_list('id', flat=True)
        )

        if not submission_classification_ids.intersection(
            reviewer_classification_ids
        ):
            raise serializers.ValidationError(
                (
                    f'Reviewer {reviewer.id} does not match the selected '
                    'classifications.'
                )
            )

        return reviewer

    def save(self):
        submission = self.context['submission']
        reviewers = self.context['reviewers']
        assigned_by = self.context['request'].user
        assignments = []

        for reviewer in reviewers:
            assignment, created = (
                SubmissionReviewerAssignment.objects.get_or_create(
                    submission=submission,
                    reviewer=reviewer,
                    defaults={
                        'assigned_by': assigned_by,
                    },
                )
            )

            was_reactivated = False
            if not assignment.is_active:
                was_reactivated = True
                assignment.is_active = True
                assignment.status = ReviewerAssignmentStatus.PENDING
                assignment.responded_at = None
                assignment.reviewer_response_reminder_sent_at = None
                assignment.assigned_by = assigned_by
                assignment.save(
                    update_fields=[
                        'is_active',
                        'status',
                        'responded_at',
                        'reviewer_response_reminder_sent_at',
                        'assigned_by',
                    ]
                )

            if created or was_reactivated:
                notify_user(
                    user=reviewer,
                    title='Reviewer Assignment',
                    message=(
                        'You have been assigned to review the submission '
                        f'"{submission.title or submission}".'
                    ),
                    notification_type='review',
                )

            assignments.append(assignment)

        if submission.status != SubmissionStatus.UNDER_PEER_REVIEW:
            submission.status = SubmissionStatus.UNDER_PEER_REVIEW
            submission.save(update_fields=['status', 'updated_at'])

        return assignments


# --------------------------------------------------
# Main Submission Serializer
# --------------------------------------------------

class SubmissionSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(
        source='author.full_name',
        read_only=True,
    )

    assigned_editor_name = serializers.CharField(
        source='assigned_editor.full_name',
        read_only=True,
    )

    article_type_name = serializers.CharField(
        source='article_type.name',
        read_only=True,
    )

    classifications_data = ClassificationSerializer(
        source='classifications',
        many=True,
        read_only=True,
    )

    authors = SubmissionAuthorSerializer(
        many=True,
        read_only=True,
    )

    submission_files = SubmissionFileSerializer(
        many=True,
        read_only=True,
    )

    versions = SubmissionVersionSerializer(
        many=True,
        read_only=True,
    )

    reviewer_assignments = SubmissionReviewerAssignmentSerializer(
        many=True,
        read_only=True,
    )

    # Draft workflow status
    sections = serializers.ReadOnlyField()
    completed_sections = serializers.ReadOnlyField()
    total_sections = serializers.ReadOnlyField()
    is_ready_to_submit = serializers.ReadOnlyField()

    # Accept classification IDs from frontend
    classification_ids = serializers.PrimaryKeyRelatedField(
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
            'assigned_editor',
            'assigned_editor_name',
            'article_type_name',
            'status',
            'submitted_at',
            'created_at',
            'updated_at',
            'versions',
            'reviewer_assignments',
            'sections',
            'completed_sections',
            'total_sections',
            'is_ready_to_submit',
        ]

    def validate_classification_ids(self, value):
        unique_ids = {classification.id for classification in value}

        if len(unique_ids) < MIN_CLASSIFICATIONS_REQUIRED:
            raise serializers.ValidationError(
                (
                    f'Select at least {MIN_CLASSIFICATIONS_REQUIRED} '
                    'classifications.'
                )
            )

        return value

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

        active_statuses = [
            SubmissionStatus.UNDER_EDITOR_REVIEW,
            SubmissionStatus.UNDER_PEER_REVIEW,
            SubmissionStatus.MINOR_REVISION,
            SubmissionStatus.MAJOR_REVISION,
        ]
        editor = User.objects.filter(
            is_active=True,
            is_editor=True,
        ).exclude(
            id=submission.author_id,
        ).annotate(
            active_submission_count=Count(
                'assigned_editor_submissions',
                filter=Q(
                    assigned_editor_submissions__status__in=active_statuses
                ),
            )
        ).order_by(
            'active_submission_count',
            'id',
        ).first()

        if not editor:
            raise serializers.ValidationError(
                'No active editor is available for assignment.'
            )

        submission.assigned_editor = editor
        submission.status = SubmissionStatus.UNDER_EDITOR_REVIEW
        submission.submitted_at = timezone.now()
        submission.save()

        notify_user(
            user=editor,
            title='New Submission Assigned',
            message=(
                'A new submission has been assigned to you for editor review: '
                f'"{submission.title or submission}".'
            ),
            notification_type='submission',
        )

        return submission


# --------------------------------------------------
# Resubmit Serializer
# --------------------------------------------------

class ResubmitSerializer(serializers.Serializer):
    manuscript_file = serializers.FileField()
    revision_notes = serializers.CharField(
        required=False,
        allow_blank=True,
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

        submission.status = SubmissionStatus.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save()

        return submission
