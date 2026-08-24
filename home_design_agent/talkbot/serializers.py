from rest_framework import serializers

from .models import Conversation, CustomerProfile, Message
from .strategy import FIELD_LABELS, conversion_missing


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = (
            'id', 'role', 'content', 'client_id', 'intent', 'emotion', 'question_asked',
            'metadata', 'created_at',
        )
        read_only_fields = fields


class CustomerProfileSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()
    emotion_display = serializers.CharField(source='get_emotion_display', read_only=True)
    persona_display = serializers.CharField(source='get_persona_type_display', read_only=True)
    completion = serializers.SerializerMethodField()
    conversion_missing = serializers.SerializerMethodField()
    conversion_ready = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProfile
        fields = (
            'id', 'name', 'phone', 'city', 'community', 'area', 'room_type', 'style',
            'situation', 'household', 'has_kids', 'kids_age', 'has_elderly', 'pets',
            'income_tier', 'budget_min', 'budget_max', 'decision_power', 'recent_events',
            'desired_timeline', 'emotion', 'emotion_display', 'persona_type', 'persona_display',
            'pain_points', 'trust_score', 'intent_score', 'missing_fields', 'completion',
            'consent_to_contact', 'conversion_missing', 'conversion_ready', 'updated_at',
        )
        read_only_fields = fields

    def get_completion(self, obj):
        total = 9
        return max(0, min(100, round((total - len(obj.missing_fields or [])) / total * 100)))

    def get_phone(self, obj):
        phone = obj.phone or ''
        return f'{phone[:3]}****{phone[-4:]}' if len(phone) >= 7 else phone

    def get_conversion_missing(self, obj):
        return [FIELD_LABELS.get(field, field) for field in conversion_missing(obj)]

    def get_conversion_ready(self, obj):
        return not conversion_missing(obj)


class ConversationSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    profile = CustomerProfileSerializer(read_only=True)
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = (
            'id', 'title', 'stage', 'stage_display', 'status', 'status_display',
            'last_action', 'summary', 'project', 'order', 'profile', 'messages',
            'created_at', 'updated_at',
        )
        read_only_fields = fields


class ConversationListSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    profile = CustomerProfileSerializer(read_only=True)
    message_count = serializers.IntegerField(source='message_count_value', read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            'id', 'title', 'stage', 'stage_display', 'status', 'last_action', 'summary',
            'project', 'order', 'profile', 'message_count', 'last_message', 'created_at', 'updated_at',
        )

    def get_last_message(self, obj):
        latest_messages = getattr(obj, 'latest_messages', None)
        message = latest_messages[0] if latest_messages else None
        return MessageSerializer(message).data if message else None


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=1000, trim_whitespace=True)
    client_message_id = serializers.RegexField(
        r'^[A-Za-z0-9._:-]{8,64}$',
        required=False,
        allow_blank=False,
        help_text='客户端生成的幂等标识；网络重试时保持不变。',
    )


class ConvertSerializer(serializers.Serializer):
    consent = serializers.BooleanField(
        help_text='用户明确确认同意平台根据本次装修需求联系。',
    )
