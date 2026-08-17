"""角色（Role）定义：复用 Django Group，不引入独立角色表。

权限使用 ``app_label.codename`` 字符串描述，由 ``seed_roles`` 管理命令解析
并绑定到对应 Group。超级用户（is_superuser=True）始终绕过对象级权限。
"""


ROLE_CUSTOMER = 'customer'
ROLE_DESIGNER = 'designer'
ROLE_OPERATIONS = 'operations'
ROLE_ADMIN = 'admin'

ROLE_LABELS = {
    ROLE_CUSTOMER: '普通用户',
    ROLE_DESIGNER: '设计师',
    ROLE_OPERATIONS: '运营',
    ROLE_ADMIN: '管理员',
}

DEFAULT_ROLE = ROLE_CUSTOMER

# 默认角色及其最小权限集。设计域权限由 Django 为各模型自动生成
# （view_* / add_* / change_* / delete_*），命令中做存在性校验，缺省时跳过。
ROLE_PERMISSIONS = {
    ROLE_CUSTOMER: [],
    ROLE_DESIGNER: [
        'design.view_project',
        'design.view_designscheme',
        'design.view_renderjob',
    ],
    ROLE_OPERATIONS: [
        'auth.view_user',
        'design.view_project',
        'design.view_designscheme',
        'design.view_renderjob',
        'design.view_homeorder',
        'design.change_homeorder',
        'design.view_lead',
        'design.change_lead',
    ],
    ROLE_ADMIN: [
        'auth.add_user',
        'auth.change_user',
        'auth.delete_user',
        'auth.view_user',
    ],
}


def get_user_roles(user):
    """返回用户的角色名列表。"""
    if user is None or not user.is_authenticated:
        return []
    return list(user.groups.values_list('name', flat=True))


def user_has_role(user, role):
    """超级用户直接放行，其余按 Group 判断。"""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=role).exists()
