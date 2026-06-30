from django.conf import settings
from django.db import models
import secrets

MIN_CLASSIFICATIONS_REQUIRED = 4


class ArticleType(models.Model):
    """
    Step 1: Choose your article type.
    """

    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SubmissionFileType(models.Model):
    """
    Examples:
    - Manuscript
    - Cover Letter
    - Figure
    - Table
    - Response to Reviewers
    - Supplementary Material
    - Graphical Abstract
    - Highlights
    - Audio / Video
    """

    name = models.CharField(max_length=255, unique=True)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    allow_multiple = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Submission File Type'
        verbose_name_plural = 'Submission File Types'

    def __str__(self):
        return self.name


class Classification(models.Model):
    name = models.CharField(
        max_length=255,
        unique=True,
    )
    is_active = models.BooleanField(
        default=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ContributorRole(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SubmissionStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SUBMITTED = 'submitted', 'Submitted'
    UNDER_EDITOR_REVIEW = 'under_editor_review', 'Under Editor Review'
    UNDER_PEER_REVIEW = 'under_peer_review', 'Under Peer Review'
    MINOR_REVISION = 'minor_revision', 'Minor Revision'
    MAJOR_REVISION = 'major_revision', 'Major Revision'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    WITHDRAWN = 'withdrawn', 'Withdrawn'
    PUBLISHED = 'published', 'Published'


class ReviewerAssignmentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'


class ReviewerRecommendation(models.TextChoices):
    ACCEPT = 'accept', 'Accept'
    REJECT = 'reject', 'Reject'
    MINOR_REVISION = 'minor_revision', 'Minor Revision'
    MAJOR_REVISION = 'major_revision', 'Major Revision'


class RefereeConfidence(models.TextChoices):
    CONFIDENT = 'confident', 'With confidence'
    NOT_ABLE = 'not_able', 'I am not able to referee this mss'


class RefereeSuitabilityRating(models.TextChoices):
    RATING_100 = '100', '100%'
    RATING_75 = '75', '75%'
    RATING_50 = '50', '50%'
    RATING_25 = '25', '25%'
    RATING_0 = '0', '0%'


class PaperQualityRating(models.TextChoices):
    EXCELLENT = 'excellent', 'Excellent'
    SIGNIFICANT = 'significant', 'Significant'
    MARGINAL = 'marginal', 'Marginal'
    NON_SIGNIFICANT = 'non_significant', 'Non Significant'
    ERRONEOUS_OR_TRIVIAL = 'erroneous_or_trivial', 'Erroneous or Trivial'


class PaperValueRating(models.TextChoices):
    WORTH_PUBLISHING = 'worth_publishing', 'Worth publishing'
    MINOR_MODIFICATIONS = (
        'minor_modifications',
        'Worth publishing when revised - minor modifications',
    )
    MAJOR_MODIFICATIONS = (
        'major_modifications',
        'Worth publishing when revised - major modifications',
    )
    NOT_WORTH_PUBLISHING = 'not_worth_publishing', 'Not worth publishing'


class ManuscriptClassificationRecommendation(models.TextChoices):
    REVIEW = 'review', 'A review'
    PAPER = 'paper', 'A paper'
    COMMUNICATION = 'communication', 'A communication'
    TECHNICAL_NOTE = 'technical_note', 'A technical note'


class Submission(models.Model):
    REFERENCE_PREFIX = 'JBSIP-'

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    assigned_editor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_editor_submissions'
    )

    # Step 1
    article_type = models.ForeignKey(
        ArticleType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submissions'
    )

    # Step 3
    title = models.CharField(max_length=500, blank=True)
    abstract = models.TextField(blank=True)
    keywords = models.TextField(blank=True)

    # Step 5
    open_access = models.BooleanField(null=True, blank=True)

    # Step 6
    classifications = models.ManyToManyField(
        Classification,
        blank=True,
        related_name='submissions'
    )

    # Step 7
    funding_information = models.TextField(blank=True)
    conflict_of_interest = models.TextField(blank=True)
    suggested_reviewers = models.TextField(blank=True)
    additional_notes = models.TextField(blank=True)

    # Step 8
    ethics_accepted = models.BooleanField(default=False)

    # Workflow
    manuscript_reference = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=50,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.DRAFT
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f'Draft #{self.pk}'

    @classmethod
    def generate_manuscript_reference(cls):
        while True:
            reference = f'{cls.REFERENCE_PREFIX}{secrets.randbelow(900000) + 100000}'
            if not cls.objects.filter(manuscript_reference=reference).exists():
                return reference

    @property
    def sections(self):
        return {
            'article_type': bool(self.article_type_id),

            'submission_files': (
                SubmissionFileType.objects.filter(
                    is_required=True,
                    is_active=True
                ).count()
                ==
                self.submission_files.filter(
                    file_type__is_required=True,
                    file_type__is_active=True
                ).values('file_type').distinct().count()
            ),

            'title_abstract_keywords': bool(
                self.title and self.abstract and self.keywords
            ),

            'author_details': self.authors.exists(),

            'open_access': self.open_access is not None,

            'classifications': (
                self.classifications.filter(is_active=True).count()
                >= MIN_CLASSIFICATIONS_REQUIRED
            ),

            'additional_information': bool(
                self.funding_information or
                self.conflict_of_interest or
                self.suggested_reviewers or
                self.additional_notes
            ),

            'ethics_accepted': self.ethics_accepted,
        }

    @property
    def total_sections(self):
        return 7

    @property
    def completed_sections(self):
        s = self.sections
        required = [
            'article_type',
            'submission_files',
            'title_abstract_keywords',
            'author_details',
            'open_access',
            'classifications',
            'additional_information',
        ]
        return sum(1 for key in required if s[key])

    @property
    def is_ready_to_submit(self):
        return (
            self.completed_sections == self.total_sections
            and self.ethics_accepted
        )


class SubmissionAuthor(models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='authors'
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    institution = models.CharField(max_length=255)
    email = models.EmailField()

    contributor_roles = models.ManyToManyField(
        ContributorRole,
        blank=True,
        related_name='submission_authors'
    )

    is_corresponding_author = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['submission'],
                condition=models.Q(is_corresponding_author=True),
                name='unique_corresponding_author_per_submission'
            )
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class SubmissionFile(models.Model):
    submission = models.ForeignKey(
        'Submission',
        on_delete=models.CASCADE,
        related_name='submission_files',
    )
    file_type = models.ForeignKey(
        'SubmissionFileType',
        on_delete=models.CASCADE,
        related_name='files',
    )
    file = models.FileField(
        upload_to='submissions/files/'
    )
    original_filename = models.CharField(
        max_length=255,
        blank=True,
    )
    file_size = models.PositiveBigIntegerField(
        default=0,
    )
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_submission_files',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.file:
            self.original_filename = self.file.name.split('/')[-1]
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Delete the actual file from storage first
        if self.file:
            self.file.delete(save=False)

        # Delete the database record
        super().delete(*args, **kwargs)

    def __str__(self):
        return f'{self.submission.title} - {self.file_type.name}'

class SubmissionVersion(models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    version_number = models.PositiveIntegerField()
    manuscript_file = models.FileField(
        upload_to='submissions/versions/'
    )
    revision_notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = ('submission', 'version_number')

    def __str__(self):
        return f'{self.submission} - v{self.version_number}'


class SubmissionReviewerAssignment(models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='reviewer_assignments'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_assignments'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_reviewers'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=ReviewerAssignmentStatus.choices,
        default=ReviewerAssignmentStatus.PENDING
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    reviewer_response_reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-assigned_at']
        constraints = [
            models.UniqueConstraint(
                fields=['submission', 'reviewer'],
                name='unique_reviewer_assignment_per_submission'
            )
        ]

    def __str__(self):
        return f'{self.submission} -> {self.reviewer}'


class SubmissionReviewerReport(models.Model):
    assignment = models.OneToOneField(
        SubmissionReviewerAssignment,
        on_delete=models.CASCADE,
        related_name='review_report'
    )
    review_report_complete = models.BooleanField(default=False)
    ready_to_transfer_to_editor = models.BooleanField(default=False)
    recommendation = models.CharField(
        max_length=20,
        choices=ReviewerRecommendation.choices,
        blank=True,
    )
    reviewer_comments_to_author = models.TextField(blank=True)
    confidential_comments_to_editor = models.TextField(blank=True)

    paper_referee_confidence = models.CharField(
        max_length=20,
        choices=RefereeConfidence.choices,
        blank=True,
    )
    referee_suitability_rating = models.CharField(
        max_length=3,
        choices=RefereeSuitabilityRating.choices,
        blank=True,
    )
    paper_quality_rating = models.CharField(
        max_length=30,
        choices=PaperQualityRating.choices,
        blank=True,
    )
    paper_value_rating = models.CharField(
        max_length=30,
        choices=PaperValueRating.choices,
        blank=True,
    )
    suitable_for_different_journal = models.BooleanField(
        null=True,
        blank=True,
    )

    content_original_work = models.BooleanField(
        null=True,
        blank=True,
    )
    content_well_organised = models.BooleanField(
        null=True,
        blank=True,
    )
    content_abstract_adequate = models.BooleanField(
        null=True,
        blank=True,
    )
    content_technically_sound = models.BooleanField(
        null=True,
        blank=True,
    )
    content_practical_application = models.BooleanField(
        null=True,
        blank=True,
    )
    content_references_adequate = models.BooleanField(
        null=True,
        blank=True,
    )

    presentation_explains_clearly = models.BooleanField(
        null=True,
        blank=True,
    )
    presentation_methods_included = models.BooleanField(
        null=True,
        blank=True,
    )
    presentation_demonstrates_value = models.BooleanField(
        null=True,
        blank=True,
    )
    presentation_language_clear = models.BooleanField(
        null=True,
        blank=True,
    )

    manuscript_classification = models.CharField(
        max_length=20,
        choices=ManuscriptClassificationRecommendation.choices,
        blank=True,
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Reviewer report for assignment #{self.assignment_id}'
