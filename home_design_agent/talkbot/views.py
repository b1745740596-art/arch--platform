from django.db import transaction
from django.db.models import Count, Prefetch
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from design.serializers import HomeOrderSerializer

from .engine import convert_conversation, create_conversation, process_message
from .llm import load_deepseek_config
from .models import Conversation, KnowledgeDocument, Message, TalkWorkflow
from .serializers import (
    ConversationListSerializer,
    ConversationSerializer,
    ConvertSerializer,
    CustomerProfileSerializer,
    MessageSerializer,
    SendMessageSerializer,
)
from .throttles import (
    TalkBotConvertThrottle,
    TalkBotIPThrottle,
    TalkBotMessageThrottle,
    TalkBotSessionThrottle,
)


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    deepseek = load_deepseek_config()
    cache_ready = False
    try:
        cache.set('talkbot:health', 'ok', timeout=10)
        cache_ready = cache.get('talkbot:health') == 'ok'
    except Exception:  # noqa: BLE001 - health must report dependency failure as JSON
        cache_ready = False
    payload = {
        'status': 'ok',
        'app': 'talkbot',
        'workflow_ready': TalkWorkflow.objects.filter(is_active=True).exists(),
        'knowledge_ready': KnowledgeDocument.objects.filter(is_active=True, base__is_active=True).exists(),
        'cache_ready': cache_ready,
        'llm_provider': 'deepseek',
        'llm_enabled': deepseek.enabled,
        'llm_configured': deepseek.configured,
        'llm_model': deepseek.model,
    }
    llm_ready = not deepseek.enabled or deepseek.configured
    ready = payload['workflow_ready'] and payload['knowledge_ready'] and cache_ready and llm_ready
    payload['ready'] = ready
    if not ready:
        payload['status'] = 'degraded'
    return Response(payload, status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE)


class ConversationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer
    http_method_names = ('get', 'post', 'head', 'options')

    def get_throttles(self):
        throttle_class = {
            'create': TalkBotSessionThrottle,
            'messages': TalkBotMessageThrottle,
            'convert': TalkBotConvertThrottle,
        }.get(self.action)
        return [throttle_class(), TalkBotIPThrottle()] if throttle_class else []

    def get_queryset(self):
        queryset = (
            Conversation.objects.filter(user=self.request.user)
            .select_related('profile', 'project', 'order')
        )
        if self.action == 'list':
            return (
                queryset.annotate(message_count_value=Count('messages'))
                .order_by('-updated_at', '-id')
                .prefetch_related(
                    Prefetch(
                        'messages',
                        queryset=Message.objects.order_by('-id')[:1],
                        to_attr='latest_messages',
                    ),
                )
            )
        return queryset.prefetch_related('messages')

    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer

    def create(self, request, *args, **kwargs):
        conversation = create_conversation(request.user)
        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='messages')
    def messages(self, request, pk=None):
        conversation = self.get_object()
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = process_message(
                conversation,
                serializer.validated_data['content'],
                client_id=serializer.validated_data.get('client_message_id', ''),
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        conversation.refresh_from_db()
        profile = conversation.profile
        user_message = conversation.messages.filter(
            role=Message.Role.USER,
            client_id=message.client_id,
        ).first()
        return Response({
            'message': MessageSerializer(message).data,
            'user_message': MessageSerializer(user_message).data if user_message else None,
            'profile': CustomerProfileSerializer(profile).data,
            'conversation': {
                'id': conversation.id,
                'title': conversation.title,
                'stage': conversation.stage,
                'stage_display': conversation.get_stage_display(),
                'status': conversation.status,
                'last_action': conversation.last_action,
                'summary': conversation.summary,
            },
        })

    @action(detail=True, methods=['get'], url_path='profile')
    def profile(self, request, pk=None):
        return Response(CustomerProfileSerializer(self.get_object().profile).data)

    @action(detail=True, methods=['post'], url_path='convert')
    def convert(self, request, pk=None):
        conversation = self.get_object()
        serializer = ConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = convert_conversation(
                conversation,
                consent=serializer.validated_data['consent'],
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response({
            'detail': '项目订单已创建。',
            'order': HomeOrderSerializer(order).data,
            'conversation': ConversationSerializer(
                Conversation.objects.select_related('profile', 'project', 'order').get(pk=conversation.pk),
            ).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='close')
    @transaction.atomic
    def close(self, request, pk=None):
        conversation = get_object_or_404(
            Conversation.objects.filter(user=request.user).select_for_update(),
            pk=pk,
        )
        if conversation.status == Conversation.Status.ACTIVE:
            conversation.status = Conversation.Status.CLOSED
            conversation.stage = Conversation.Stage.FOLLOW_UP
            conversation.save(update_fields=['status', 'stage', 'updated_at'])
        return Response(ConversationSerializer(conversation).data)
