from rest_framework.permissions import BasePermission


class IsStaff(BasePermission):
    message = "Staff access required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )