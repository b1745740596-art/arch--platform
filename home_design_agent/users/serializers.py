from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import UserProfile
from .services import consume_password_reset_token

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """当前用户资料：账号主键与权限字段只读，资料字段可写。"""

    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_staff = serializers.BooleanField(source='user.is_staff', read_only=True)
    is_superuser = serializers.BooleanField(source='user.is_superuser', read_only=True)
    roles = serializers.SerializerMethodField()
    free_credits = serializers.IntegerField(read_only=True)
    purchased_credits = serializers.IntegerField(read_only=True)
    total_credits = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = (
            'id', 'username', 'email', 'display_name', 'phone', 'avatar',
            'bio', 'locale', 'timezone', 'email_verified',
            'free_credits', 'purchased_credits', 'total_credits',
            'is_staff', 'is_superuser', 'roles', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'email_verified', 'free_credits', 'purchased_credits',
            'created_at', 'updated_at',
        )

    def get_roles(self, obj):
        return list(obj.user.groups.values_list('name', flat=True))

    def get_total_credits(self, obj):
        return (obj.free_credits or 0) + (obj.purchased_credits or 0)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if instance.display_name and instance.user.first_name != instance.display_name:
            instance.user.first_name = instance.display_name
            instance.user.save(update_fields=['first_name'])
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('当前密码不正确。')
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value

    def save(self):
        from django.contrib.auth import update_session_auth_hash

        request = self.context['request']
        user = request.user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        update_session_auth_hash(request, user)
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return (value or '').strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.IntegerField(min_value=1)
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        try:
            user = User.objects.get(pk=attrs['uid'], is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError({'uid': '无效的重置链接。'})
        validate_password(attrs['new_password'], user)
        if consume_password_reset_token(user, attrs['token']) is None:
            raise serializers.ValidationError({'token': '重置链接无效或已过期。'})
        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class AdminUserSerializer(serializers.ModelSerializer):
    """后台用户管理：支持创建/编辑用户、绑定角色组与设置密码。"""

    display_name = serializers.CharField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(required=False, allow_blank=True, default='')
    roles = serializers.SlugRelatedField(
        slug_field='name', queryset=Group.objects.all(), many=True, required=False,
    )
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, min_length=8,
    )

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name',
            'display_name', 'phone', 'roles',
            'is_active', 'is_staff', 'is_superuser',
            'password', 'date_joined', 'last_login',
        )
        read_only_fields = ('id', 'date_joined', 'last_login')

    def validate_username(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('用户名不能为空。')
        qs = User.objects.filter(username=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('用户名已存在。')
        return value

    def validate_email(self, value):
        value = (value or '').strip().lower()
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if value and qs.exists():
            raise serializers.ValidationError('邮箱已被占用。')
        return value

    def _extract_profile_data(self, validated_data):
        data = {}
        for key in ('display_name', 'phone'):
            if key in validated_data:
                data[key] = validated_data.pop(key) or ''
            elif not self.partial:
                data[key] = ''
        return data

    def _sync_profile(self, user, profile_data):
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'free_credits': getattr(settings, 'PAYMENT_FREE_CREDITS', 5)},
        )
        changed = False
        for key, value in profile_data.items():
            if value is not None and getattr(profile, key) != value:
                setattr(profile, key, value)
                changed = True
        if changed:
            profile.save()
        return profile

    def create(self, validated_data):
        profile_data = self._extract_profile_data(validated_data)
        roles = validated_data.pop('roles', [])
        password = validated_data.pop('password', None)
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        if roles:
            user.groups.set(roles)
        self._sync_profile(user, profile_data)
        return user

    def update(self, instance, validated_data):
        profile_data = self._extract_profile_data(validated_data)
        roles = validated_data.pop('roles', None)
        password = validated_data.pop('password', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.groups.set(roles)
        self._sync_profile(instance, profile_data)
        return instance
