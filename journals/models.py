import os

from django.conf import settings
from django.db import models


class Subject(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


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
    name = models.CharField(max_length=255, unique=True)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='classifications',
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

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


class Submission(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions'
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
    subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submissions'
    )

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

            'classifications': self.classifications.exists(),

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
        Submission,
        on_delete=models.CASCADE,
        related_name='submission_files'
    )

    file_type = models.ForeignKey(
        SubmissionFileType,
        on_delete=models.PROTECT,
        related_name='files'
    )

    file = models.FileField(upload_to='submissions/files/')

    original_filename = models.CharField(
        max_length=500,
        blank=True
    )

    file_size = models.PositiveBigIntegerField(
        null=True,
        blank=True
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.file:
            self.original_filename = os.path.basename(self.file.name)
            if hasattr(self.file, 'size'):
                self.file_size = self.file.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.file_type.name} - {self.original_filename}'


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
