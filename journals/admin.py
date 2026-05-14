# journals/admin.py
# Replace your entire journals/admin.py with this updated version.

from django.contrib import admin
from .models import (
    Subject,
    ArticleType,
    Classification,
    Submission,
    SubmissionVersion,
)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(ArticleType)
class ArticleTypeAdmin(admin.ModelAdmin):
    # display_order was removed from the model,
    # so it must not be referenced here.
    list_display = (
        'name',
        'is_active',
    )
    list_filter = (
        'is_active',
    )
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'is_active')
    list_filter = ('is_active', 'subject')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'author',
        'status',
        'created_at',
        'submitted_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'author__email', 'author__full_name')
    ordering = ('-created_at',)


@admin.register(SubmissionVersion)
class SubmissionVersionAdmin(admin.ModelAdmin):
    list_display = (
        'submission',
        'version_number',
        'uploaded_by',
        'created_at',
    )
    ordering = ('-created_at',)