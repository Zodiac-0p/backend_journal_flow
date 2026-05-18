from django.contrib import admin

from .models import (
    Subject,
    ArticleType,
    Classification,
    Submission,
    SubmissionVersion,
    ContributorRole,
    SubmissionAuthor,
    SubmissionFileType,
    SubmissionFile,
)


# ==================================================
# MASTER DATA ADMIN
# ==================================================

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
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
        'subject',
        'is_active',
    )
    list_filter = (
        'is_active',
        'subject',
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


# ==================================================
# SUBMISSION ADMIN
# ==================================================

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'author',
        'article_type',
        'subject',
        'status',
        'created_at',
        'submitted_at',
    )
    list_filter = (
        'status',
        'article_type',
        'subject',
        'created_at',
    )
    search_fields = (
        'title',
        'author__email',
        'author__full_name',
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
    ]


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
