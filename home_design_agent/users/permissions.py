from rest_framework.permissions import BasePermission


class IsActiveUser(BasePermission):
    """已登录且账号未被停用。"""

    message = '账号已停用，请联系管理员。'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )


class CanManageUsers(BasePermission):
    """用户管理权限：超级用户，或持有 auth.view_user 权限的角色。"""

    message = '没有管理用户的权限。'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.has_perm('auth.view_user'))
        )


class IsSelfOrStaff(BasePermission):
    """对象级权限：本人可访问；管理员可访问任意用户。"""

    message = '只能操作自己的账号。'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.has_perm('auth.view_user'):
            return True
        target_user_id = getattr(obj, 'pk', None)
        return target_user_id == user.pk
