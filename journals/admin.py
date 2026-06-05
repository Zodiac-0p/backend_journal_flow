from django.contrib import admin

from .models import (
    ArticleType,
    Classification,
    Submission,
    SubmissionVersion,
    ContributorRole,
    SubmissionAuthor,
    SubmissionFileType,
    SubmissionFile,
    SubmissionReviewerAssignment,
    SubmissionReviewerReport,
)


# ==================================================
# MASTER DATA ADMIN
# ==================================================


@admin.register(ArticleType)
class ArticleTypeAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'name',
    )
    ordering = (
        'name',
    )


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_active',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'name',
    )
    ordering = (
        'name',
    )


@admin.register(ContributorRole)
class ContributorRoleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'name',
    )
    ordering = (
        'name',
    )


@admin.register(SubmissionFileType)
class SubmissionFileTypeAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_required',
        'allow_multiple',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_required',
        'allow_multiple',
        'is_active',
    )
    search_fields = (
        'name',
    )
    ordering = (
        'name',
    )


# ==================================================
# INLINE ADMIN
# ==================================================

class SubmissionAuthorInline(admin.TabularInline):
    model = SubmissionAuthor
    extra = 0
    fields = (
        'order',
        'first_name',
        'last_name',
        'institution',
        'email',
        'is_corresponding_author',
    )
    ordering = (
        'order',
    )


class SubmissionFileInline(admin.TabularInline):
    model = SubmissionFile
    extra = 0
    fields = (
        'file_type',
        'file',
        'original_filename',
        'file_size',
        'uploaded_by',
        'created_at',
    )
    readonly_fields = (
        'original_filename',
        'file_size',
        'uploaded_by',
        'created_at',
    )


class SubmissionReviewerAssignmentInline(admin.TabularInline):
    model = SubmissionReviewerAssignment
    extra = 0
    fields = (
        'reviewer',
        'assigned_by',
        'assigned_at',
        'status',
        'responded_at',
        'reviewer_response_reminder_sent_at',
        'is_active',
    )
    readonly_fields = (
        'assigned_at',
        'responded_at',
        'reviewer_response_reminder_sent_at',
    )
    autocomplete_fields = (
        'reviewer',
        'assigned_by',
    )


# ==================================================
# SUBMISSION ADMIN
# ==================================================

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'author',
        'assigned_editor',
        'article_type',
        'status',
        'classification_count',
        'active_reviewer_assignment_count',
        'created_at',
        'submitted_at',
    )
    list_filter = (
        'status',
        'assigned_editor',
        'article_type',
        'created_at',
    )
    search_fields = (
        'title',
        'author__email',
        'author__full_name',
        'assigned_editor__email',
        'assigned_editor__full_name',
    )
    autocomplete_fields = (
        'author',
        'assigned_editor',
    )
    ordering = (
        '-created_at',
    )
    filter_horizontal = (
        'classifications',
    )
    inlines = [
        SubmissionAuthorInline,
        SubmissionFileInline,
        SubmissionReviewerAssignmentInline,
    ]

    def classification_count(self, obj):
        return obj.classifications.count()
    classification_count.short_description = 'Classifications'

    def active_reviewer_assignment_count(self, obj):
        return obj.reviewer_assignments.filter(is_active=True).count()
    active_reviewer_assignment_count.short_description = 'Active Reviewers'


@admin.register(SubmissionAuthor)
class SubmissionAuthorAdmin(admin.ModelAdmin):
    list_display = (
        'submission',
        'order',
        'first_name',
        'last_name',
        'email',
        'institution',
        'is_corresponding_author',
    )
    list_filter = (
        'is_corresponding_author',
        'institution',
    )
    search_fields = (
        'first_name',
        'last_name',
        'email',
        'institution',
        'submission__title',
    )
    ordering = (
        'submission',
        'order',
    )
    filter_horizontal = (
        'contributor_roles',
    )


@admin.register(SubmissionFile)
class SubmissionFileAdmin(admin.ModelAdmin):
    list_display = (
        'submission',
        'file_type',
        'original_filename',
        'file_size',
        'uploaded_by',
        'created_at',
    )
    list_filter = (
        'file_type',
        'created_at',
    )
    search_fields = (
        'submission__title',
        'original_filename',
    )
    readonly_fields = (
        'original_filename',
        'file_size',
        'created_at',
    )


@admin.register(SubmissionVersion)
class SubmissionVersionAdmin(admin.ModelAdmin):
    list_display = (
        'submission',
        'version_number',
        'uploaded_by',
        'created_at',
    )
    search_fields = (
        'submission__title',
        'uploaded_by__email',
    )
    ordering = (
        '-created_at',
    )


@admin.register(SubmissionReviewerAssignment)
class SubmissionReviewerAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'submission',
        'reviewer',
        'assigned_by',
        'assigned_at',
        'status',
        'responded_at',
        'reviewer_response_reminder_sent_at',
        'is_active',
    )
    list_filter = (
        'status',
        'is_active',
        'assigned_at',
    )
    search_fields = (
        'submission__title',
        'reviewer__email',
        'reviewer__full_name',
        'assigned_by__email',
    )
    ordering = (
        '-assigned_at',
    )
    autocomplete_fields = (
        'submission',
        'reviewer',
        'assigned_by',
    )


@admin.register(SubmissionReviewerReport)
class SubmissionReviewerReportAdmin(admin.ModelAdmin):
    list_display = (
        'assignment',
        'recommendation',
        'review_report_complete',
        'ready_to_transfer_to_editor',
        'submitted_at',
        'updated_at',
    )
    list_filter = (
        'review_report_complete',
        'ready_to_transfer_to_editor',
        'recommendation',
        'submitted_at',
    )
    search_fields = (
        'assignment__submission__title',
        'assignment__reviewer__email',
        'assignment__reviewer__full_name',
    )
    autocomplete_fields = (
        'assignment',
    )
