from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ConversationViewSet, health


router = DefaultRouter()
router.register('sessions', ConversationViewSet, basename='talkbot-session')

urlpatterns = [path('health/', health, name='talkbot-health'), *router.urls]
