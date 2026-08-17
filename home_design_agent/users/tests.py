"""用户系统接口测试。

覆盖：个人资料、修改密码、找回/重置密码、后台用户管理权限。
运行方式：cd home_design_agent && .venv/bin/python manage.py test users
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import PasswordResetToken, UserProfile

User = get_user_model()

ME_URL = '/api/users/me/'
CHANGE_PASSWORD_URL = '/api/users/change-password/'
RESET_REQUEST_URL = '/api/users/password-reset/'
RESET_CONFIRM_URL = '/api/users/password-reset/confirm/'
ADMIN_USERS_URL = '/api/users/admin/users/'


class MeViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret123')

    def test_anonymous_forbidden(self):
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_creates_profile_and_returns_payload(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(ME_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'alice')
        self.assertEqual(response.data['roles'], [])
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_patch_updates_profile_and_syncs_first_name(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            ME_URL,
            {'display_name': 'Alice', 'phone': '13800000000', 'bio': 'hello'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.display_name, 'Alice')
        self.assertEqual(self.user.profile.phone, '13800000000')
        self.assertEqual(self.user.first_name, 'Alice')


class ChangePasswordViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bob', password='oldpass123')

    def test_anonymous_forbidden(self):
        response = self.client.post(CHANGE_PASSWORD_URL, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_changes_password(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            CHANGE_PASSWORD_URL,
            {'old_password': 'oldpass123', 'new_password': 'newpass123'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))

    def test_rejects_wrong_old_password(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            CHANGE_PASSWORD_URL,
            {'old_password': 'wrongpass', 'new_password': 'newpass123'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('old_password', response.data)

    def test_rejects_short_new_password(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            CHANGE_PASSWORD_URL,
            {'old_password': 'oldpass123', 'new_password': 'short'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEBUG=True,
)
class PasswordResetFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='carol',
            email='carol@example.com',
            password='secret123',
        )

    def test_unknown_email_returns_generic_success(self):
        response = self.client.post(
            RESET_REQUEST_URL,
            {'email': 'nobody@example.com'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn('debug', response.data)

    def test_known_email_creates_token_and_sends_email(self):
        response = self.client.post(
            RESET_REQUEST_URL,
            {'email': 'carol@example.com'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        token = PasswordResetToken.objects.get(user=self.user, used_at__isnull=True)
        self.assertTrue(token.is_valid)
        self.assertIn('debug', response.data)
        self.assertEqual(response.data['debug']['uid'], self.user.pk)
        self.assertIn('reset_url', response.data['debug'])

    def test_confirm_resets_password_and_consumes_token(self):
        request_response = self.client.post(
            RESET_REQUEST_URL,
            {'email': 'carol@example.com'},
            format='json',
        )
        raw_token = request_response.data['debug']['token']

        response = self.client.post(
            RESET_CONFIRM_URL,
            {
                'uid': self.user.pk,
                'token': raw_token,
                'new_password': 'brandnew123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('brandnew123'))
        token = PasswordResetToken.objects.get(user=self.user)
        self.assertIsNotNone(token.used_at)

    def test_confirm_rejects_reused_token(self):
        request_response = self.client.post(
            RESET_REQUEST_URL,
            {'email': 'carol@example.com'},
            format='json',
        )
        raw_token = request_response.data['debug']['token']

        payload = {
            'uid': self.user.pk,
            'token': raw_token,
            'new_password': 'brandnew123',
        }
        first = self.client.post(RESET_CONFIRM_URL, payload, format='json')
        second = self.client.post(RESET_CONFIRM_URL, payload, format='json')

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)


class AdminUserViewSetTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='root',
            email='root@example.com',
            password='rootpass123',
        )
        self.regular = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='userpass123',
        )

    def test_anonymous_forbidden(self):
        response = self.client.get(ADMIN_USERS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_forbidden(self):
        self.client.force_authenticate(self.regular)
        response = self.client.get(ADMIN_USERS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_can_list(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(ADMIN_USERS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {item['username'] for item in response.data['results']}
        self.assertIn('user1', usernames)

    def test_superuser_can_create_user_with_role(self):
        self.client.force_authenticate(self.admin)
        Group.objects.create(name='designer')

        response = self.client.post(
            ADMIN_USERS_URL,
            {
                'username': 'designer1',
                'email': 'designer1@example.com',
                'password': 'secret123',
                'display_name': 'Designer One',
                'phone': '13900000000',
                'roles': ['designer'],
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='designer1')
        self.assertEqual(user.profile.display_name, 'Designer One')
        self.assertEqual(list(user.groups.values_list('name', flat=True)), ['designer'])

    def test_operations_user_with_permission_can_list(self):
        group = Group.objects.create(name='operations')
        permission = Permission.objects.get(
            content_type__app_label='auth',
            codename='view_user',
        )
        group.permissions.add(permission)
        self.regular.groups.add(group)

        self.client.force_authenticate(self.regular)
        response = self.client.get(ADMIN_USERS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SeedRolesCommandTests(APITestCase):
    def test_creates_expected_groups(self):
        call_command('seed_roles', verbosity=0)

        names = set(Group.objects.values_list('name', flat=True))
        self.assertTrue({'customer', 'designer', 'operations', 'admin'} <= names)

