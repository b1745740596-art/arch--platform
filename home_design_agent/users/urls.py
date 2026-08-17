from django.urls import path

from . import views

app_name = 'users'

admin_user_list = views.AdminUserViewSet.as_view({'get': 'list', 'post': 'create'})
admin_user_detail = views.AdminUserViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy',
})

urlpatterns = [
    path('me/', views.MeView.as_view(), name='me'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('admin/users/', admin_user_list, name='admin-user-list'),
    path('admin/users/<int:pk>/', admin_user_detail, name='admin-user-detail'),
]
