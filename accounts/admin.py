from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, RoleChoice, Discipline


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    # Columns shown in user list page
    list_display = (
        'email',
        'full_name',
        'primary_role',
        'is_reviewer',
        'is_editor',
        'is_editorial_manager',
        'is_super_admin',
        'is_active',
        'created_at',
    )

    # Filters in right sidebar
    list_filter = (
        'is_reviewer',
        'is_editor',
        'is_editorial_manager',
        'is_super_admin',
        'is_active',
        'is_staff',
        'role_choice',
        'disciplines',
    )

    # Search box
    search_fields = (
        'email',
        'username',
        'full_name',
        'phone',
        'affiliation',
        'organization',
        'job_title',
        'expertise',
    )

    ordering = ('-created_at',)

    # Many-to-many selection UI
    filter_horizontal = (
        'groups',
        'user_permissions',
        'disciplines',
    )

    # Add user form fields
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'username',
                    'full_name',
                    'password1',
                    'password2',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                ),
            },
        ),
    )

    # Edit user form fields
    fieldsets = (
        ('Authentication', {
            'fields': (
                'email',
                'username',
                'password',
            )
        }),

        ('Personal Information', {
            'fields': (
                'full_name',
                'phone',
                'affiliation',
                'organization',
                'job_title',
                'expertise',
                'role_choice',
                'disciplines',
            )
        }),

        ('Publication Roles', {
            'fields': (
                'is_reviewer',
                'is_editor',
                'is_editorial_manager',
                'is_super_admin',
            )
        }),

        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            )
        }),

        ('Important Dates', {
            'fields': (
                'last_login',
                'date_joined',
                'created_at',
                'updated_at',
            )
        }),
    )

    # Read-only fields
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_login',
        'date_joined',
    )


# ----------------------------------------------------------------------
# Role Choices Admin
# ----------------------------------------------------------------------
@admin.register(RoleChoice)
class RoleChoiceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_at',)


# ----------------------------------------------------------------------
# Discipline Admin
# ----------------------------------------------------------------------
@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_at',)