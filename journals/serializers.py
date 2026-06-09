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
    SubmissionReviewerReport,
    ReviewerAssignmentStatus,
    ReviewerRecommendation,
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


class ReviewerAssignmentSubmissionSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(
        source='author.full_name',
        read_only=True,
    )
    article_type_name = serializers.CharField(
        source='article_type.name',
        read_only=True,
    )

    class Meta:
        model = Submission
        fields = [
            'id',
            'title',
            'status',
            'author',
            'author_name',
            'article_type',
            'article_type_name',
            'submitted_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class SubmissionReviewerReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionReviewerReport
        fields = [
            'id',
            'assignment',
            'review_report_complete',
            'ready_to_transfer_to_editor',
            'recommendation',
            'reviewer_comments_to_author',
            'confidential_comments_to_editor',
            'paper_referee_confidence',
            'referee_suitability_rating',
            'paper_quality_rating',
            'paper_value_rating',
            'suitable_for_different_journal',
            'content_original_work',
            'content_well_organised',
            'content_abstract_adequate',
            'content_technically_sound',
            'content_practical_application',
            'content_references_adequate',
            'presentation_explains_clearly',
            'presentation_methods_included',
            'presentation_demonstrates_value',
            'presentation_language_clear',
            'manuscript_classification',
            'submitted_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'assignment',
            'submitted_at',
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)

        ready_to_transfer = attrs.get(
            'ready_to_transfer_to_editor',
            getattr(
                self.instance,
                'ready_to_transfer_to_editor',
                False,
            ),
        )
        report_complete = attrs.get(
            'review_report_complete',
            getattr(self.instance, 'review_report_complete', False),
        )

        if ready_to_transfer and not report_complete:
            raise serializers.ValidationError({
                'review_report_complete': [
                    'Set this to true before transferring the report.'
                ]
            })

        if ready_to_transfer:
            required_fields = [
                'recommendation',
                'paper_referee_confidence',
                'referee_suitability_rating',
                'paper_quality_rating',
                'paper_value_rating',
                'suitable_for_different_journal',
                'content_original_work',
                'content_well_organised',
                'content_abstract_adequate',
                'content_technically_sound',
                'content_practical_application',
                'content_references_adequate',
                'presentation_explains_clearly',
                'presentation_methods_included',
                'presentation_demonstrates_value',
                'presentation_language_clear',
                'manuscript_classification',
            ]

            errors = {}
            for field_name in required_fields:
                value = attrs.get(
                    field_name,
                    getattr(self.instance, field_name, None)
                    if self.instance else None,
                )
                if value in (None, ''):
                    errors[field_name] = [
                        (
                            'This field is required when '
                            'ready_to_transfer_to_editor is true.'
                        )
                    ]

            if errors:
                raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        if validated_data.get('ready_to_transfer_to_editor'):
            validated_data['submitted_at'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get(
            'ready_to_transfer_to_editor',
            instance.ready_to_transfer_to_editor,
        ):
            validated_data['submitted_at'] = timezone.now()
        else:
            validated_data['submitted_at'] = None
        return super().update(instance, validated_data)


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


class ReviewerAssignmentListSerializer(serializers.ModelSerializer):
    submission = ReviewerAssignmentSubmissionSerializer(read_only=True)
    assigned_by_name = serializers.CharField(
        source='assigned_by.full_name',
        read_only=True,
    )

    class Meta:
        model = SubmissionReviewerAssignment
        fields = [
            'id',
            'submission',
            'assigned_by',
            'assigned_by_name',
            'assigned_at',
            'status',
            'responded_at',
            'reviewer_response_reminder_sent_at',
            'is_active',
        ]
        read_only_fields = fields


class ReviewerAssignmentDetailSerializer(serializers.ModelSerializer):
    submission = ReviewerAssignmentSubmissionSerializer(read_only=True)
    reviewer = ReviewerCandidateSerializer(read_only=True)
    assigned_by_name = serializers.CharField(
        source='assigned_by.full_name',
        read_only=True,
    )
    review_report = SubmissionReviewerReportSerializer(read_only=True)

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
            'review_report',
        ]
        read_only_fields = fields


class SubmissionReviewReportListSerializer(serializers.ModelSerializer):
    submission = ReviewerAssignmentSubmissionSerializer(
        source='assignment.submission',
        read_only=True,
    )
    reviewer = ReviewerCandidateSerializer(
        source='assignment.reviewer',
        read_only=True,
    )
    assignment_id = serializers.IntegerField(
        source='assignment.id',
        read_only=True,
    )
    assignment_status = serializers.CharField(
        source='assignment.status',
        read_only=True,
    )
    responded_at = serializers.DateTimeField(
        source='assignment.responded_at',
        read_only=True,
    )

    class Meta:
        model = SubmissionReviewerReport
        fields = [
            'id',
            'submission',
            'assignment_id',
            'assignment_status',
            'reviewer',
            'review_report_complete',
            'ready_to_transfer_to_editor',
            'recommendation',
            'reviewer_comments_to_author',
            'confidential_comments_to_editor',
            'paper_referee_confidence',
            'referee_suitability_rating',
            'paper_quality_rating',
            'paper_value_rating',
            'suitable_for_different_journal',
            'content_original_work',
            'content_well_organised',
            'content_abstract_adequate',
            'content_technically_sound',
            'content_practical_application',
            'content_references_adequate',
            'presentation_explains_clearly',
            'presentation_methods_included',
            'presentation_demonstrates_value',
            'presentation_language_clear',
            'manuscript_classification',
            'responded_at',
            'submitted_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class EditorDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=[
            SubmissionStatus.ACCEPTED,
            SubmissionStatus.REJECTED,
            SubmissionStatus.MINOR_REVISION,
            SubmissionStatus.MAJOR_REVISION,
        ]
    )
    editor_comment = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        submission = self.context['submission']
        ready_reports_count = submission.reviewer_assignments.filter(
            review_report__ready_to_transfer_to_editor=True
        ).count()

        if ready_reports_count == 0:
            raise serializers.ValidationError(
                'At least one transferred reviewer report is required.'
            )

        if submission.status not in [
            SubmissionStatus.UNDER_EDITOR_REVIEW,
            SubmissionStatus.UNDER_PEER_REVIEW,
        ]:
            raise serializers.ValidationError(
                'Editor decisions can only be applied during review.'
            )

        return attrs


class SendReviewCommentsToAuthorSerializer(serializers.Serializer):
    review_report_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
    )

    def validate(self, attrs):
        submission = self.context['submission']
        report_ids = attrs['review_report_ids']

        if len(set(report_ids)) != len(report_ids):
            raise serializers.ValidationError(
                'Review report IDs must be unique.'
            )

        reports = list(
            SubmissionReviewerReport.objects.filter(
                id__in=report_ids,
                assignment__submission=submission,
                ready_to_transfer_to_editor=True,
            ).select_related(
                'assignment',
                'assignment__reviewer',
                'assignment__submission',
            ).order_by('id')
        )

        if len(reports) != len(report_ids):
            raise serializers.ValidationError(
                'One or more review reports are invalid for this submission.'
            )

        reports_with_comments = [
            report
            for report in reports
            if report.reviewer_comments_to_author.strip()
        ]

        if not reports_with_comments:
            raise serializers.ValidationError(
                'Selected review reports do not contain reviewer comments to author.'
            )

        self.context['reports'] = reports_with_comments
        return attrs


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
    def get_missing_requirements(self, submission):
        missing_requirements = {}

        if not submission.article_type_id:
            missing_requirements['article_type'] = (
                'Select an article type.'
            )

        required_file_types = SubmissionFileType.objects.filter(
            is_required=True,
            is_active=True,
        )
        uploaded_required_file_type_ids = set(
            submission.submission_files.filter(
                file_type__is_required=True,
                file_type__is_active=True,
            ).values_list('file_type_id', flat=True)
        )
        missing_file_types = list(
            required_file_types.exclude(
                id__in=uploaded_required_file_type_ids
            ).values_list('name', flat=True)
        )
        if missing_file_types:
            missing_requirements['submission_files'] = {
                'message': 'Upload all required submission files.',
                'missing_file_types': missing_file_types,
            }

        missing_text_fields = [
            field_name
            for field_name in ['title', 'abstract', 'keywords']
            if not getattr(submission, field_name)
        ]
        if missing_text_fields:
            missing_requirements['title_abstract_keywords'] = {
                'message': 'Complete title, abstract, and keywords.',
                'missing_fields': missing_text_fields,
            }

        if not submission.authors.exists():
            missing_requirements['author_details'] = (
                'Add at least one author.'
            )

        if submission.open_access is None:
            missing_requirements['open_access'] = (
                'Select an open access option.'
            )

        active_classification_count = submission.classifications.filter(
            is_active=True
        ).count()
        if active_classification_count < MIN_CLASSIFICATIONS_REQUIRED:
            missing_requirements['classifications'] = {
                'message': (
                    f'Select at least {MIN_CLASSIFICATIONS_REQUIRED} active '
                    'classifications.'
                ),
                'selected_count': active_classification_count,
                'required_count': MIN_CLASSIFICATIONS_REQUIRED,
            }

        if not any([
            submission.funding_information,
            submission.conflict_of_interest,
            submission.suggested_reviewers,
            submission.additional_notes,
        ]):
            missing_requirements['additional_information'] = {
                'message': (
                    'Complete at least one additional information field.'
                ),
                'accepted_fields': [
                    'funding_information',
                    'conflict_of_interest',
                    'suggested_reviewers',
                    'additional_notes',
                ],
            }

        if not submission.ethics_accepted:
            missing_requirements['ethics_accepted'] = (
                'Accept the ethics policy before final submission.'
            )

        return missing_requirements

    def save(self, submission):
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

        if not submission.manuscript_reference:
            submission.manuscript_reference = (
                Submission.generate_manuscript_reference()
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
                f'"{submission.title or submission}" '
                f'(Reference: {submission.manuscript_reference}).'
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

        editor = submission.assigned_editor
        if editor:
            notify_user(
                user=editor,
                title='Revised Submission Received',
                message=(
                    'A revised manuscript has been resubmitted for '
                    f'"{submission.title or submission}" '
                    f'(Reference: {submission.manuscript_reference}).'
                ),
                notification_type='submission',
            )

        return submission
