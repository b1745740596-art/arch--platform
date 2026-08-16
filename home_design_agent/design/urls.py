from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'design'

router = DefaultRouter()
router.register('owners', views.OwnerViewSet)
router.register('projects', views.ProjectViewSet)
router.register('schemes', views.DesignSchemeViewSet)
router.register('leads', views.LeadViewSet)
router.register('requirements', views.CustomerRequirementViewSet)
router.register('providers', views.ServiceProviderViewSet)
router.register('designers', views.DesignerViewSet)
router.register('furnitures', views.FurnitureViewSet)
router.register('renders', views.RenderJobViewSet)
router.register('workflows', views.RenderWorkflowViewSet)

urlpatterns = [
    path('health/', views.health, name='health'),
    path('auth/register/', views.register_user, name='auth-register'),
    path('auth/login/', views.login_user, name='auth-login'),
    path('auth/logout/', views.logout_user, name='auth-logout'),
    path('auth/me/', views.current_user, name='auth-me'),
    path('prompt-modules/options/', views.prompt_module_options, name='prompt-module-options'),
    path('prompt-modules/suggest/', views.prompt_module_suggest, name='prompt-module-suggest'),
    path('', include(router.urls)),
]
