"""Design-domain API security regression tests."""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpRequest
from django.middleware.csrf import get_token
from django.test import Client
from rest_framework import serializers as drf_serializers, status
from rest_framework.test import APITestCase

from users.models import UserProfile, VerificationConfig

from .admin import GenerationConfigAdminForm
from .serializers import RenderJobSerializer
from .models import (
    CustomerRequirement,
    DesignScheme,
    GenerationConfig,
    HomeReport,
    Lead,
    Owner,
    Project,
    PromptModule,
    RenderJob,
    RenderWorkflow,
    ServiceProvider,
    WorkflowStep,
)


User = get_user_model()


class AppReleaseTests(APITestCase):
    def test_release_feed_includes_external_apk_fallback(self):
        response = self.client.get('/api/design/app-version/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['version'], '1.3.7')
        self.assertEqual(response.data['build'], 14)
        self.assertEqual(
            response.data['external_apk_url'],
            'https://github.com/b1745740596-art/arch--platform/'
            'releases/download/apk/app-release.apk',
        )


class GenerationConfigSecretTests(APITestCase):
    def setUp(self):
        self.config = GenerationConfig.objects.create(name='default')

    def _form(self, **overrides):
        data = {
            'name': 'default',
            'talkbot_enabled': 'on',
            'talkbot_api_base': 'https://api.deepseek.com',
            'talkbot_api_key': '',
            'talkbot_model': 'deepseek-v4-flash',
        }
        data.update(overrides)
        return GenerationConfigAdminForm(data=data, instance=self.config)

    def test_admin_form_encrypts_key_and_blank_input_preserves_it(self):
        secret = 'sk-admin-secret-value'
        form = self._form(talkbot_api_key=secret)
        self.assertTrue(form.is_valid(), form.errors)
        config = form.save()

        self.assertNotEqual(config.talkbot_api_key_encrypted, secret)
        self.assertNotIn(secret, config.talkbot_api_key_encrypted)
        self.assertEqual(config.get_talkbot_api_key(), secret)

        blank_form = self._form()
        self.assertTrue(blank_form.is_valid(), blank_form.errors)
        blank_form.save()
        self.config.refresh_from_db()
        self.assertEqual(self.config.get_talkbot_api_key(), secret)

    def test_admin_form_can_explicitly_clear_key(self):
        self.config.set_talkbot_api_key('sk-delete-me')
        self.config.save(update_fields=('talkbot_api_key_encrypted',))

        form = self._form(clear_talkbot_api_key='on')
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.config.refresh_from_db()
        self.assertFalse(self.config.has_talkbot_api_key)

    def test_admin_form_rejects_insecure_api_endpoint(self):
        form = self._form(talkbot_api_base='http://api.deepseek.com', talkbot_api_key='sk-test')
        self.assertFalse(form.is_valid())
        self.assertIn('talkbot_api_base', form.errors)

    def test_admin_change_page_never_renders_stored_key(self):
        secret = 'sk-never-render-this-value'
        self.config.set_talkbot_api_key(secret)
        self.config.save(update_fields=('talkbot_api_key_encrypted',))
        administrator = User.objects.create_superuser(
            username='config-admin',
            password='secret123',
            email='admin@example.com',
        )
        self.client.force_login(administrator)

        response = self.client.get(f'/admin/design/generationconfig/{self.config.pk}/change/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotContains(response, secret)
        self.assertContains(response, 'name="talkbot_api_key"')


class LoginCsrfTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='csrf-user', password='secret123')
        self.client = Client(enforce_csrf_checks=True)

    def test_session_login_requires_csrf_and_accepts_valid_token(self):
        payload = json.dumps({'username': 'csrf-user', 'password': 'secret123'})
        rejected = self.client.post(
            '/api/design/auth/login/',
            payload,
            content_type='application/json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('sessionid', rejected.cookies)

        csrf_request = HttpRequest()
        csrf_token = get_token(csrf_request)
        self.client.cookies['csrftoken'] = csrf_request.META['CSRF_COOKIE']
        accepted = self.client.post(
            '/api/design/auth/login/',
            payload,
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertIn('sessionid', accepted.cookies)


class DesignOwnershipIsolationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user(username='alice-design', password='secret123')
        self.bob = User.objects.create_user(username='bob-design', password='secret123')
        UserProfile.objects.create(user=self.alice, display_name='Alice', phone='13800000001')
        UserProfile.objects.create(user=self.bob, display_name='Bob', phone='13800000002')
        self.alice_owner = Owner.objects.create(name='Alice', phone='13800000001', city='上海')
        self.bob_owner = Owner.objects.create(name='Bob', phone='13800000002', city='苏州')
        self.alice_project = Project.objects.create(
            user=self.alice, owner=self.alice_owner, title='Alice Home', city='上海',
        )
        self.bob_project = Project.objects.create(
            user=self.bob, owner=self.bob_owner, title='Bob Home', city='苏州',
        )
        self.alice_scheme = DesignScheme.objects.create(
            project=self.alice_project, name='Alice Scheme', style='原木',
        )
        self.bob_scheme = DesignScheme.objects.create(
            project=self.bob_project, name='Bob Scheme', style='现代',
        )
        self.alice_lead = Lead.objects.create(
            project=self.alice_project, contact_name='Alice', contact_phone='13800000001',
        )
        self.bob_lead = Lead.objects.create(
            project=self.bob_project, contact_name='Bob', contact_phone='13800000002',
        )
        self.alice_requirement = CustomerRequirement.objects.create(
            user=self.alice, name='Alice', phone='13800000001',
        )
        self.bob_requirement = CustomerRequirement.objects.create(
            user=self.bob, name='Bob', phone='13800000002',
        )
        self.alice_render = RenderJob.objects.create(
            project=self.alice_project, raw_photo='raw_photos/alice.jpg',
        )
        self.bob_render = RenderJob.objects.create(
            project=self.bob_project, raw_photo='raw_photos/bob.jpg',
        )
        self.alice_report = HomeReport.objects.create(
            user=self.alice, project=self.alice_project, title='Alice Report',
        )
        self.bob_report = HomeReport.objects.create(
            user=self.bob, project=self.bob_project, title='Bob Report',
        )
        self.client.force_authenticate(self.alice)

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _ids(self, response):
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        return {item['id'] for item in payload}

    def test_owner_pii_is_scoped_and_api_is_read_only(self):
        response = self.client.get('/api/design/owners/')
        self.assertEqual(self._ids(response), {self.alice_owner.id})
        self.assertEqual(
            self.client.get(f'/api/design/owners/{self.bob_owner.id}/').status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/design/owners/{self.alice_owner.id}/', {'phone': '13900000000'}, format='json',
            ).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_leads_schemes_requirements_and_renders_are_user_scoped(self):
        cases = (
            ('leads', self.alice_lead.id, self.bob_lead.id),
            ('schemes', self.alice_scheme.id, self.bob_scheme.id),
            ('requirements', self.alice_requirement.id, self.bob_requirement.id),
            ('renders', self.alice_render.id, self.bob_render.id),
        )
        for endpoint, own_id, other_id in cases:
            response = self.client.get(f'/api/design/{endpoint}/')
            self.assertIn(own_id, self._ids(response), endpoint)
            self.assertNotIn(other_id, self._ids(response), endpoint)
            self.assertEqual(
                self.client.get(f'/api/design/{endpoint}/{other_id}/').status_code,
                status.HTTP_404_NOT_FOUND,
                endpoint,
            )

    def test_cannot_create_lead_for_another_users_project(self):
        response = self.client.post(
            '/api/design/leads/',
            {'project': self.bob_project.id, 'contact_name': 'Alice', 'contact_phone': '13800000001'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lead_rejects_cross_project_scheme_and_unverified_contact(self):
        no_consent = self.client.post(
            '/api/design/leads/',
            {
                'project': self.alice_project.id,
                'contact_name': 'Alice',
                'contact_phone': '13800000001',
            },
            format='json',
        )
        self.assertEqual(no_consent.status_code, status.HTTP_400_BAD_REQUEST)

        other_phone = self.client.post(
            '/api/design/leads/',
            {
                'project': self.alice_project.id,
                'contact_name': 'Alice',
                'contact_phone': '13800000002',
                'consent': True,
            },
            format='json',
        )
        self.assertEqual(other_phone.status_code, status.HTTP_400_BAD_REQUEST)

        cross_scheme = self.client.post(
            '/api/design/leads/',
            {
                'project': self.alice_project.id,
                'scheme': self.bob_scheme.id,
                'contact_name': 'Alice',
                'contact_phone': '13800000001',
                'consent': True,
            },
            format='json',
        )
        self.assertEqual(cross_scheme.status_code, status.HTTP_400_BAD_REQUEST)

        accepted = self.client.post(
            '/api/design/leads/',
            {
                'project': self.alice_project.id,
                'scheme': self.alice_scheme.id,
                'contact_name': 'Alice',
                'contact_phone': '13800000001',
                'consent': True,
            },
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_201_CREATED, accepted.data)
        self.assertEqual(accepted.data['contact_phone'], '13800000001')

    def test_project_cannot_be_transferred_or_linked_to_foreign_owner(self):
        transfer = self.client.patch(
            f'/api/design/projects/{self.alice_project.id}/',
            {'user': self.bob.id, 'title': 'Still Alice'},
            format='json',
        )
        self.assertEqual(transfer.status_code, status.HTTP_200_OK)
        self.alice_project.refresh_from_db()
        self.assertEqual(self.alice_project.user_id, self.alice.id)

        foreign_owner = self.client.patch(
            f'/api/design/projects/{self.alice_project.id}/',
            {'owner': self.bob_owner.id},
            format='json',
        )
        self.assertEqual(foreign_owner.status_code, status.HTTP_403_FORBIDDEN)

    def test_report_and_order_cannot_reference_foreign_data(self):
        move_report = self.client.patch(
            f'/api/design/reports/{self.alice_report.id}/',
            {'project': self.bob_project.id},
            format='json',
        )
        self.assertEqual(move_report.status_code, status.HTTP_403_FORBIDDEN)

        cross_order = self.client.post(
            '/api/design/orders/',
            {'project': self.alice_project.id, 'report': self.bob_report.id, 'title': 'Cross order'},
            format='json',
        )
        self.assertEqual(cross_order.status_code, status.HTTP_403_FORBIDDEN)

    def test_order_requires_consent_but_defaults_to_no_identity_verification(self):
        self.alice.profile.phone = ''
        self.alice.profile.save(update_fields=('phone', 'updated_at'))
        no_consent = self.client.post(
            '/api/design/orders/',
            {
                'project': self.alice_project.id,
                'title': 'Alice order',
            },
            format='json',
        )
        self.assertEqual(no_consent.status_code, status.HTTP_400_BAD_REQUEST)

        accepted = self.client.post(
            '/api/design/orders/',
            {
                'project': self.alice_project.id,
                'title': 'Alice order',
                'consent': True,
            },
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_201_CREATED, accepted.data)
        self.assertEqual(accepted.data['customer_phone'], '')

    def test_order_phone_verification_can_be_enabled_from_backend(self):
        VerificationConfig.objects.update_or_create(
            name='default',
            defaults={
                'phone_verification_enabled': True,
                'require_phone_verification_for_order': True,
            },
        )
        rejected = self.client.post(
            '/api/design/orders/',
            {
                'project': self.alice_project.id,
                'title': 'Alice order',
                'customer_phone': '13800000002',
                'consent': True,
            },
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

        accepted = self.client.post(
            '/api/design/orders/',
            {
                'project': self.alice_project.id,
                'title': 'Alice verified order',
                'customer_phone': '13800000001',
                'consent': True,
            },
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_201_CREATED, accepted.data)
        self.assertEqual(accepted.data['customer_phone'], '13800000001')

    def test_order_email_verification_can_be_enabled_from_backend(self):
        VerificationConfig.objects.update_or_create(
            name='default',
            defaults={
                'email_verification_enabled': True,
                'require_email_verification_for_order': True,
            },
        )
        rejected = self.client.post(
            '/api/design/orders/',
            {'project': self.alice_project.id, 'title': 'Email order', 'consent': True},
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

        self.alice.profile.email_verified = True
        self.alice.profile.verified_email = 'alice@example.com'
        self.alice.profile.save(update_fields=('email_verified', 'verified_email', 'updated_at'))
        accepted = self.client.post(
            '/api/design/orders/',
            {'project': self.alice_project.id, 'title': 'Email order', 'consent': True},
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_201_CREATED, accepted.data)

    def test_provider_catalog_is_read_only(self):
        response = self.client.post(
            '/api/design/providers/',
            {'name': 'Injected provider', 'kind': ServiceProvider.Kind.DESIGN},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_requirement_chain_is_owned_and_visible_to_submitter(self):
        response = self.client.post(
            '/api/design/requirements/',
            {
                'name': 'Alice',
                'phone': '13800000001',
                'city': '上海',
                'room_type': '客厅',
                'style': '原木',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        requirement = CustomerRequirement.objects.get(pk=response.data['id'])
        project = Project.objects.get(requirement_summary__room_type='客厅')
        self.assertEqual(requirement.user, self.alice)
        self.assertEqual(project.user, self.alice)
        self.assertEqual(project.leads.get().contact_phone, '13800000001')
        self.assertIn(project.id, self._ids(self.client.get('/api/design/projects/')))

    def test_requirement_cannot_mutate_owner_using_another_users_phone(self):
        response = self.client.post(
            '/api/design/requirements/',
            {
                'name': 'Injected name',
                'phone': '13800000002',
                'city': '北京',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.bob_owner.refresh_from_db()
        self.assertEqual(self.bob_owner.name, 'Bob')
        self.assertEqual(self.bob_owner.city, '苏州')
        self.assertFalse(CustomerRequirement.objects.filter(name='Injected name').exists())

    def test_render_requirement_rejects_direct_identifiers_before_model_use(self):
        serializer = RenderJobSerializer()
        cases = (
            '联系人：张三，上海市浦东新区世纪大道100号1栋2单元',
            '身份证 310101 19900101 123X',
            '电话 010 12345678',
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(drf_serializers.ValidationError) as caught:
                serializer.validate_requirement(value)
            self.assertIn('个人信息', str(caught.exception))


class DesignPromptCoachTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='designer-chat-user', password='secret123')
        self.client.force_authenticate(self.user)
        self.base_draft = {
            'has_images': True,
            'images': [{'id': 'image-1', 'room_type': '客厅'}],
            'plan_name': '我家客厅',
            'room_type': '客厅',
            'style': '现代简约',
            'budget_tier': '品质',
            'requirement': '',
            'module_codes': [],
        }

    def post_turn(self, **overrides):
        payload = {
            'message': '',
            'stage': '',
            'active_image_id': '',
            'completed_stages': [],
            'history': [],
            'draft': dict(self.base_draft),
            'locale': 'zh-CN',
        }
        payload.update(overrides)
        with patch('design.prompt_coach._refine_with_deepseek', return_value=(None, 'rules')):
            return self.client.post('/api/design/prompt-coach/turn/', payload, format='json')

    def test_prompt_coach_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/design/prompt-coach/turn/', {}, format='json')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_prompt_coach_starts_with_upload_when_image_is_missing(self):
        draft = dict(self.base_draft, has_images=False, images=[])
        response = self.post_turn(draft=draft)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['stage'], 'upload')
        self.assertIn('设计师', response.data['message'])
        self.assertFalse(response.data['ready_to_generate'])

    def test_prompt_coach_asks_and_assigns_each_uploaded_image_room(self):
        draft = dict(
            self.base_draft,
            room_type='',
            images=[
                {'id': 'image-1', 'room_type': ''},
                {'id': 'image-2', 'room_type': ''},
            ],
        )
        first = self.post_turn(draft=draft)
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        self.assertEqual(first.data['stage'], 'image_room')
        self.assertEqual(first.data['active_image_id'], 'image-1')
        self.assertIn('第 1 张', first.data['message'])

        assigned_draft = dict(draft)
        second = self.post_turn(
            draft=assigned_draft,
            message='这是客厅',
            stage='image_room',
            active_image_id='image-1',
            completed_stages=['upload'],
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(second.data['form_patch']['image_rooms'], [
            {'image_id': 'image-1', 'room_type': '客厅'},
        ])
        self.assertEqual(second.data['stage'], 'image_room')
        self.assertEqual(second.data['active_image_id'], 'image-2')
        self.assertIn('第 2 张', second.data['message'])

        final_draft = dict(
            draft,
            images=[
                {'id': 'image-1', 'room_type': '客厅'},
                {'id': 'image-2', 'room_type': ''},
            ],
        )
        final = self.post_turn(
            draft=final_draft,
            message='这是厨房',
            stage='image_room',
            active_image_id='image-2',
            completed_stages=['upload'],
        )
        self.assertEqual(final.status_code, status.HTTP_200_OK, final.data)
        self.assertEqual(final.data['form_patch']['image_rooms'], [
            {'image_id': 'image-2', 'room_type': '厨房'},
        ])
        self.assertEqual(final.data['stage'], 'function')
        self.assertIn('image_room', final.data['completed_stages'])

    def test_prompt_coach_skips_completed_form_fields_and_asks_one_sop_question(self):
        response = self.post_turn()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['stage'], 'function')
        self.assertEqual(
            response.data['completed_stages'][:4],
            ['upload', 'image_room', 'style', 'budget'],
        )
        self.assertEqual(len(response.data['quick_replies']), 3)
        self.assertLessEqual(sum(response.data['message'].count(mark) for mark in '。！？'), 2)

    def test_prompt_coach_appends_requirement_and_advances(self):
        response = self.post_turn(
            message='三口之家，需要充足收纳',
            stage='function',
            completed_stages=['upload', 'image_room', 'style', 'budget'],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['stage'], 'atmosphere')
        self.assertIn('三口之家', response.data['form_patch']['requirement'])
        self.assertIn('function', response.data['completed_stages'])

    def test_prompt_coach_maps_atmosphere_to_known_prompt_modules(self):
        for group, code in (
            (PromptModule.Group.LIGHTING, 'coach-lighting'),
            (PromptModule.Group.MOOD, 'coach-mood'),
            (PromptModule.Group.COLOR, 'coach-color'),
        ):
            PromptModule.objects.create(
                code=code,
                name=code,
                group=group,
                prompt_fragment=code,
                weight=10,
            )
        response = self.post_turn(
            message='明亮温暖',
            stage='atmosphere',
            completed_stages=['upload', 'image_room', 'style', 'budget', 'function'],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['stage'], 'constraints')
        self.assertEqual(
            set(response.data['form_patch']['module_codes']),
            {'coach-lighting', 'coach-mood', 'coach-color'},
        )

    def test_prompt_coach_rejects_personal_data_without_advancing(self):
        response = self.post_turn(
            message='我的手机号是13800138000，三口之家',
            stage='function',
            completed_stages=['upload', 'image_room', 'style', 'budget'],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['stage'], 'function')
        self.assertEqual(response.data['form_patch'], {})
        self.assertIn('隐私', response.data['message'])

    def test_prompt_coach_selects_image_edit_workflow_without_exposing_steps(self):
        generic = RenderWorkflow.objects.create(name='普通生成', is_default=True)
        WorkflowStep.objects.create(
            workflow=generic,
            kind=WorkflowStep.Kind.GENERATE_IMAGE,
            order=10,
        )
        image_edit = RenderWorkflow.objects.create(name='室内图生图', tags=['客厅', '图生图'])
        WorkflowStep.objects.create(
            workflow=image_edit,
            kind=WorkflowStep.Kind.EDIT_IMAGE,
            order=10,
        )

        response = self.post_turn()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['form_patch']['workflow_id'], image_edit.id)
        self.assertNotIn('workflow', response.data['message'].lower())
