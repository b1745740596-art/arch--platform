from django.conf import settings
from django.contrib.auth import get_user_model, login
from rest_framework import viewsets
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EmailVerificationCode, SmsVerificationCode, UserProfile
from .permissions import CanManageUsers, IsActiveUser
from .serializers import (
    AdminUserSerializer,
    ChangePasswordSerializer,
    EmailBindSerializer,
    EmailCodeRequestSerializer,
    EmailLoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PhoneBindSerializer,
    PhoneLoginSerializer,
    SmsCodeRequestSerializer,
    TokenLoginSerializer,
    UserProfileSerializer,
)
from .services import (
    build_password_reset_url,
    consume_remember_token,
    create_email_code,
    create_password_reset_token,
    create_remember_token,
    create_sms_code,
    revoke_remember_token,
    send_password_reset_email,
)

User = get_user_model()


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'free_credits': getattr(settings, 'PAYMENT_FREE_CREDITS', 5)},
    )
    return profile


def _user_payload(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }


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


class PhoneBindCodeView(APIView):
    """绑定手机前发送验证码（需登录）。"""

    permission_classes = [IsAuthenticated, IsActiveUser]

    def post(self, request):
        serializer = SmsCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']

        already_bound = UserProfile.objects.exclude(user=request.user).filter(
            phone=phone,
            user__is_active=True,
        ).exists()
        if already_bound:
            return Response({'phone': ['该手机号已被其他账号绑定。']}, status=400)

        raw_code = create_sms_code(phone, SmsVerificationCode.Purpose.BIND)
        payload = {'detail': '验证码已发送。'}
        if settings.DEBUG:
            payload['debug'] = {'code': raw_code}
        return Response(payload)


class PhoneBindView(GenericAPIView):
    """验证验证码并绑定手机号（需登录）。"""

    permission_classes = [IsAuthenticated, IsActiveUser]
    serializer_class = PhoneBindSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': '手机号绑定成功。'})


class PhoneLoginCodeView(APIView):
    """验证码登录/自动注册前发送验证码。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SmsCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']

        raw_code = create_sms_code(phone, SmsVerificationCode.Purpose.LOGIN)
        payload = {'detail': '验证码已发送。'}
        if settings.DEBUG:
            payload['debug'] = {'code': raw_code}
        return Response(payload)


class PhoneLoginView(APIView):
    """使用手机号 + 验证码登录；未绑定手机号时自动注册并登录。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PhoneLoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(_user_payload(user))


class EmailBindCodeView(APIView):
    """绑定/验证邮箱前发送验证码（需登录）。"""

    permission_classes = [IsAuthenticated, IsActiveUser]

    def post(self, request):
        serializer = EmailCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        if User.objects.exclude(pk=request.user.pk).filter(email=email, is_active=True).exists():
            return Response({'email': ['该邮箱已被其他账号绑定。']}, status=400)

        raw_code = create_email_code(email, EmailVerificationCode.Purpose.BIND)
        payload = {'detail': '验证码已发送。'}
        if settings.DEBUG:
            payload['debug'] = {'code': raw_code}
        return Response(payload)


class EmailBindView(GenericAPIView):
    """验证邮箱验证码并绑定/验证邮箱（需登录）。"""

    permission_classes = [IsAuthenticated, IsActiveUser]
    serializer_class = EmailBindSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': '邮箱验证成功。'})


class EmailLoginCodeView(APIView):
    """邮箱验证码登录/自动注册前发送验证码。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = EmailCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        raw_code = create_email_code(email, EmailVerificationCode.Purpose.LOGIN)
        payload = {'detail': '验证码已发送。'}
        if settings.DEBUG:
            payload['debug'] = {'code': raw_code}
        return Response(payload)


class EmailLoginView(APIView):
    """使用邮箱 + 验证码登录；未注册邮箱时自动注册并登录。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = EmailLoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(_user_payload(user))


class RememberTokenView(APIView):
    """持久登录令牌：POST 创建，DELETE 注销当前令牌。"""

    permission_classes = [IsAuthenticated, IsActiveUser]

    def post(self, request):
        raw_token = create_remember_token(request.user)
        return Response({'token': raw_token}, status=201)

    def delete(self, request):
        raw_token = request.data.get('token') or request.query_params.get('token')
        revoke_remember_token(raw_token)
        return Response({'detail': '已注销持久登录。'})


class TokenLoginView(APIView):
    """用持久登录令牌恢复 Session 登录。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = TokenLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = consume_remember_token(serializer.validated_data['token'])
        if user is None:
            return Response({'detail': '登录已过期，请重新登录。'}, status=400)
        login(request, user)
        return Response(_user_payload(user))


class AdminUserViewSet(viewsets.ModelViewSet):
    """后台用户管理：列出/创建/编辑/删除用户与角色组。"""

    queryset = User.objects.prefetch_related('profile', 'groups').order_by('-date_joined')
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, CanManageUsers]
