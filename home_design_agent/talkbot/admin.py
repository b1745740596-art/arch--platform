from django.contrib import admin

from .models import (
    Conversation,
    CustomerProfile,
    KnowledgeBase,
    KnowledgeDocument,
    Message,
    TalkStep,
    TalkWorkflow,
)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('role', 'content', 'intent', 'emotion', 'question_asked', 'created_at')
    readonly_fields = fields
    can_delete = False
    ordering = ('created_at', 'id')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'stage', 'status', 'last_action', 'project', 'order', 'updated_at')
    list_filter = ('stage', 'status', 'last_action')
    search_fields = ('title', 'summary', 'user__username', 'profile__name', 'profile__phone')
    readonly_fields = ('workflow_log', 'created_at', 'updated_at')
    inlines = (MessageInline,)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'city', 'area', 'style', 'budget_max', 'emotion', 'trust_score', 'intent_score')
    list_filter = ('emotion', 'persona_type', 'city', 'consent_to_contact')
    search_fields = ('name', 'phone', 'city', 'community', 'situation')
    readonly_fields = ('emotion_trace', 'missing_fields', 'created_at', 'updated_at')


class TalkStepInline(admin.TabularInline):
    model = TalkStep
    extra = 1
    fields = ('order', 'kind', 'name', 'params', 'is_active', 'continue_on_error')
    ordering = ('order', 'id')


@admin.register(TalkWorkflow)
class TalkWorkflowAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'is_active', 'stop_on_error', 'updated_at')
    list_editable = ('is_active',)
    list_filter = ('is_default', 'is_active', 'stop_on_error')
    inlines = (TalkStepInline,)

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TalkStep)
class TalkStepAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'order', 'kind', 'name', 'is_active', 'continue_on_error')
    list_filter = ('workflow', 'kind', 'is_active')
    list_editable = ('order', 'is_active', 'continue_on_error')


class KnowledgeDocumentInline(admin.StackedInline):
    model = KnowledgeDocument
    extra = 1
    fields = ('title', 'content', 'tags', 'priority', 'is_active')


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active', 'updated_at')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description')
    inlines = (KnowledgeDocumentInline,)


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'base', 'priority', 'is_active', 'updated_at')
    list_filter = ('base__category', 'base', 'is_active')
    search_fields = ('title', 'content', 'tags')
