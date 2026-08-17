from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserProfile
from .permissions import CanManageUsers, IsActiveUser
from .serializers import (
    AdminUserSerializer,
    ChangePasswordSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserProfileSerializer,
)
from .services import (
    build_password_reset_url,
    create_password_reset_token,
    send_password_reset_email,
)

User = get_user_model()


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'free_credits': getattr(settings, 'PAYMENT_FREE_CREDITS', 5)},
    )
    return profile


class MeView(RetrieveUpdateAPIView):
    """当前登录用户资料：GET 读取，PATCH 局部更新。"""

    permission_classes = [IsAuthenticated, IsActiveUser]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return _get_or_create_profile(self.request.user)


class ChangePasswordView(GenericAPIView):
    """登录态下修改密码，成功后保持当前会话有效。"""

    permission_classes = [IsAuthenticated, IsActiveUser]
    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': '密码已修改。'})


class PasswordResetRequestView(APIView):
    """忘记密码：按邮箱发送重置链接，不向未注册邮箱泄露账号是否存在。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email, is_active=True).first()

        raw_token = None
        reset_url = None
        if user:
            raw_token = create_password_reset_token(user)
            reset_url = build_password_reset_url(request, user, raw_token)
            send_password_reset_email(user, raw_token, reset_url)

        payload = {'detail': '如果该邮箱已注册，重置链接将发送至该邮箱。'}
        if settings.DEBUG and raw_token:
            payload['debug'] = {
                'uid': user.pk,
                'token': raw_token,
                'reset_url': reset_url,
            }
        return Response(payload)


class PasswordResetConfirmView(APIView):
    """使用重置链接中的 uid + token 设置新密码。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': '密码已重置，请使用新密码登录。'})


class AdminUserViewSet(viewsets.ModelViewSet):
    """后台用户管理：列出/创建/编辑/删除用户与角色组。"""

    queryset = User.objects.prefetch_related('profile', 'groups').order_by('-date_joined')
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, CanManageUsers]
