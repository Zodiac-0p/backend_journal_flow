from django.db import models
from django.contrib.auth.models import AbstractUser


# ----------------------------------------------------------------------
# System Role Enum
# ----------------------------------------------------------------------
class Role(models.TextChoices):
    AUTHOR = 'author', 'Author'
    REVIEWER = 'reviewer', 'Reviewer'
    EDITOR = 'editor', 'Editor'
    EDITORIAL_MANAGER = 'editorial_manager', 'Editorial Manager'
    SUPER_ADMIN = 'super_admin', 'Super Admin'


# ----------------------------------------------------------------------
# Profile Role Choices (Managed by Editorial Manager)
# Examples:
# - Professor
# - Student > PhD Student
# - Software Developer
# ----------------------------------------------------------------------
class RoleChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ----------------------------------------------------------------------
# Disciplines (Multi-select)
# Examples:
# - Computer Science
# - Mathematics
# - Physics
# ----------------------------------------------------------------------
class Discipline(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ----------------------------------------------------------------------
# Custom User Model
# ----------------------------------------------------------------------
class User(AbstractUser):
    # Basic Information
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    # Institution Information
    affiliation = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    organization = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # Professional Information
    job_title = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    expertise = models.TextField(
        blank=True,
        null=True
    )

    # System Role Flags
    is_reviewer = models.BooleanField(default=False)
    is_editor = models.BooleanField(default=False)
    is_editorial_manager = models.BooleanField(default=False)
    is_super_admin = models.BooleanField(default=False)

    # Profile Role (single choice)
    role_choice = models.ForeignKey(
        RoleChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    # Disciplines (multiple choice)
    disciplines = models.ManyToManyField(
        Discipline,
        blank=True,
        related_name='users'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Authentication Settings
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    # String Representation
    def __str__(self):
        return self.email

    # Computed Primary Role
    @property
    def primary_role(self):
        if self.is_super_admin:
            return Role.SUPER_ADMIN
        if self.is_editorial_manager:
            return Role.EDITORIAL_MANAGER
        if self.is_editor:
            return Role.EDITOR
        if self.is_reviewer:
            return Role.REVIEWER
        return Role.AUTHOR