from rest_framework.permissions import SAFE_METHODS, BasePermission


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
    """Use Django's separate view/add/change/delete permissions per HTTP action."""

    message = '没有管理用户的权限。'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if request.method in SAFE_METHODS:
            permission = 'auth.view_user'
        elif request.method == 'POST':
            permission = 'auth.add_user'
        elif request.method in ('PUT', 'PATCH'):
            permission = 'auth.change_user'
        elif request.method == 'DELETE':
            permission = 'auth.delete_user'
        else:
            return False
        return user.has_perm(permission)

    def has_object_permission(self, request, view, obj):
        if getattr(obj, 'is_superuser', False) and not request.user.is_superuser:
            return False
        return self.has_permission(request, view)


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
