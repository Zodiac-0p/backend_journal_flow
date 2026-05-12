from rest_framework.permissions import BasePermission


class IsOwnerOrEditorialStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_super_admin:
            return True

        if request.user.is_editorial_manager:
            return True

        if request.user.is_editor:
            return True

        return obj.author == request.user


class IsEditorialManagerOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (
                request.user.is_editorial_manager or
                request.user.is_super_admin
            )
        )