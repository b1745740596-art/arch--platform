import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from design.models import Designer, DesignScheme, Furniture, Project, RenderJob
from users.models import UserProfile


class AdminMenuTests(SimpleTestCase):
    def test_every_registered_admin_page_is_in_the_sidebar(self):
        configured_urls = {
            item['url']
            for group in settings.SIMPLEUI_CONFIG['menus']
            for item in group.get('models', ())
        }
        registered_urls = {
            reverse(
                f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist',
            )
            for model in admin.site._registry
        }

        self.assertSetEqual(configured_urls, registered_urls)

    def test_every_sidebar_group_is_enabled(self):
        group_names = [group['name'] for group in settings.SIMPLEUI_CONFIG['menus']]
        self.assertEqual(settings.SIMPLEUI_CONFIG['menu_display'], group_names)

    def test_sidebar_does_not_append_duplicate_system_groups(self):
        group_names = [group['name'] for group in settings.SIMPLEUI_CONFIG['menus']]
        self.assertFalse(settings.SIMPLEUI_CONFIG['system_keep'])
        self.assertEqual(len(group_names), len(set(group_names)))


class PrivateMediaTests(TestCase):
    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_settings.enable()

        user_model = get_user_model()
        self.alice = user_model.objects.create_user('alice', password='password')
        self.bob = user_model.objects.create_user('bob', password='password')
        self.staff = user_model.objects.create_user(
            'staff', password='password', is_staff=True,
        )

        self.profile = UserProfile.objects.create(user=self.alice)
        self.profile.avatar.save(
            'alice-avatar.png', ContentFile(b'alice-avatar'), save=True,
        )

        self.project = Project.objects.create(user=self.alice, title='Alice project')
        self.project.floorplan.save(
            'alice-floorplan.png', ContentFile(b'alice-floorplan'), save=False,
        )
        self.project.raw_photo.save(
            'alice-project-photo.png', ContentFile(b'alice-project-photo'), save=False,
        )
        self.project.save()

        self.scheme = DesignScheme.objects.create(
            project=self.project,
            name='Alice scheme',
        )
        self.scheme.cover_image.save(
            'alice-scheme.png', ContentFile(b'alice-scheme'), save=True,
        )

        self.render = RenderJob(
            project=self.project,
            status=RenderJob.Status.SUCCESS,
            room_type='living-room',
            style='modern',
        )
        self.render.raw_photo.save(
            'alice-render-input.png', ContentFile(b'alice-render-input'), save=False,
        )
        self.render.result_image.save(
            'alice-render-result.png', ContentFile(b'alice-render-result'), save=False,
        )
        self.render.save()

        self.owned_files = {
            self.profile.avatar.url: b'alice-avatar',
            self.project.floorplan.url: b'alice-floorplan',
            self.project.raw_photo.url: b'alice-project-photo',
            self.scheme.cover_image.url: b'alice-scheme',
            self.render.raw_photo.url: b'alice-render-input',
            self.render.result_image.url: b'alice-render-result',
        }

    def tearDown(self):
        self.media_settings.disable()
        self.media_dir.cleanup()
        super().tearDown()

    @staticmethod
    def response_body(response):
        body = b''.join(response.streaming_content)
        response.close()
        return body

    def test_anonymous_user_cannot_read_private_media(self):
        response = self.client.get(self.profile.avatar.url)

        self.assertEqual(response.status_code, 403)

    def test_only_fixed_apk_path_is_publicly_downloadable(self):
        app_dir = Path(self.media_dir.name) / 'app'
        app_dir.mkdir()
        (app_dir / 'arch-ai.apk').write_bytes(b'android-package')
        (app_dir / 'internal.apk').write_bytes(b'internal-package')

        response = self.client.get(reverse('app-download'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.response_body(response), b'android-package')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('arch-ai.apk', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.client.get('/media/app/internal.apk').status_code, 403)

    def test_other_user_can_read_finished_render_but_not_private_source_media(self):
        self.client.force_login(self.bob)

        private_files = {
            url: content for url, content in self.owned_files.items()
            if url != self.render.result_image.url
        }
        for url in private_files:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

        response = self.client.get(self.render.result_image.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.response_body(response), b'alice-render-result')

    def test_owner_can_read_every_owned_image_field(self):
        self.client.force_login(self.alice)

        for url, expected in self.owned_files.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.response_body(response), expected)
                self.assertEqual(response['Cache-Control'], 'private, no-store')
                self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_authenticated_users_can_read_only_active_catalog_media(self):
        designer = Designer.objects.create(name='Shared designer')
        designer.avatar.save(
            'designer.png', ContentFile(b'designer-avatar'), save=True,
        )
        furniture = Furniture.objects.create(
            name='Shared sofa', category=Furniture.Category.SOFA,
        )
        furniture.image.save(
            'sofa.png', ContentFile(b'furniture-image'), save=True,
        )
        inactive_designer = Designer.objects.create(
            name='Inactive designer', is_active=False,
        )
        inactive_designer.avatar.save(
            'inactive.png', ContentFile(b'inactive-avatar'), save=True,
        )

        self.assertEqual(self.client.get(designer.avatar.url).status_code, 403)
        self.assertEqual(self.client.get(furniture.image.url).status_code, 403)
        self.client.force_login(self.alice)
        designer_response = self.client.get(designer.avatar.url)
        furniture_response = self.client.get(furniture.image.url)
        self.assertEqual(designer_response.status_code, 200)
        self.assertEqual(
            self.response_body(designer_response), b'designer-avatar',
        )
        self.assertEqual(furniture_response.status_code, 200)
        self.assertEqual(
            self.response_body(furniture_response), b'furniture-image',
        )
        self.assertEqual(self.client.get(inactive_designer.avatar.url).status_code, 404)

        self.client.force_login(self.staff)
        inactive_response = self.client.get(inactive_designer.avatar.url)
        self.assertEqual(inactive_response.status_code, 200)
        self.assertEqual(
            self.response_body(inactive_response), b'inactive-avatar',
        )

    def test_path_traversal_variants_are_rejected(self):
        outside_file = Path(self.media_dir.name).parent / 'private-media-secret.txt'
        outside_file.write_bytes(b'secret')
        self.addCleanup(outside_file.unlink, missing_ok=True)
        self.client.force_login(self.staff)

        traversal_urls = (
            '/media/%2e%2e/private-media-secret.txt',
            '/media/%252e%252e/private-media-secret.txt',
            '/media/folder%5c..%5cprivate-media-secret.txt',
            '/media/./private-media-secret.txt',
        )
        for url in traversal_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)


class PrivateShowcaseTests(TestCase):
    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_settings.enable()

        user_model = get_user_model()
        self.alice = user_model.objects.create_user('alice', password='password')
        self.bob = user_model.objects.create_user('bob', password='password')
        self.alice_project = Project.objects.create(user=self.alice, title='Alice')
        self.bob_project = Project.objects.create(user=self.bob, title='Bob')
        self.alice_render = self.create_render(
            self.alice_project, 'alice.png', b'alice-result', 'modern',
        )
        self.bob_render = self.create_render(
            self.bob_project, 'bob.png', b'bob-result', 'classic',
        )
        self.url = reverse('design:showcase-images')

    def tearDown(self):
        self.media_settings.disable()
        self.media_dir.cleanup()
        super().tearDown()

    @staticmethod
    def create_render(project, filename, content, style):
        job = RenderJob(
            project=project,
            status=RenderJob.Status.SUCCESS,
            room_type='living-room',
            style=style,
        )
        job.raw_photo.save(
            f'input-{filename}', ContentFile(b'input'), save=False,
        )
        job.result_image.save(filename, ContentFile(content), save=False)
        job.save()
        return job

    def test_showcase_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_showcase_only_returns_current_users_jobs(self):
        self.client.force_login(self.alice)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        images = response.json()['images']
        self.assertEqual([image['id'] for image in images], [self.alice_render.id])
        self.assertNotIn(str(self.bob_render.id), response.content.decode())


class BrowserSecurityHeaderTests(TestCase):
    def test_headers_survive_admin_theme_middleware_changes(self):
        response = self.client.get('/api/design/health/')
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(response['Content-Security-Policy'], "frame-ancestors 'self'")
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
