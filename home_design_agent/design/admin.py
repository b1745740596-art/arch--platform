from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse
from django.utils.html import format_html, format_html_join, mark_safe

from .models import (
    CustomerRequirement,
    Designer,
    DesignScheme,
    Furniture,
    GenerationConfig,
    HomeOrder,
    HomeReport,
    Lead,
    OrderDetail,
    Owner,
    Project,
    PromptModule,
    RenderJob,
    RenderWorkflow,
    ServiceProvider,
    WorkflowStep,
)

User = get_user_model()

# ---- 后台站点品牌 ----
admin.site.site_header = 'Arch_AI Platform 后台'
admin.site.site_title = 'Arch_AI Platform'
admin.site.index_title = '控制台'


# 重新注册用户，展示昵称与状态，提供搜索与筛选
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        'username',
        'first_name',      # 昵称
        'email',
        'is_active',
        'is_staff',
        'is_superuser',
        'last_login',
        'date_joined',
    )
    list_display_links = ('username', 'first_name')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    list_per_page = 25

    @admin.display(description='昵称', ordering='first_name')
    def nickname(self, obj):
        return obj.first_name or '-'


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'city', 'community', 'house_status', 'created_at')
    list_filter = ('house_status', 'city')
    search_fields = ('name', 'phone', 'community')


class DesignSchemeInline(admin.TabularInline):
    model = DesignScheme
    extra = 0
    fields = ('name', 'style', 'budget_tier', 'budget_min', 'budget_max', 'is_favorited', 'version')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'owner', 'city', 'community', 'area', 'status', 'created_at')
    list_filter = ('status', 'city')
    search_fields = ('title', 'community', 'owner__name', 'owner__phone')
    inlines = [DesignSchemeInline]


@admin.register(DesignScheme)
class DesignSchemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'style', 'budget_tier', 'budget_min', 'budget_max', 'is_favorited', 'version')
    list_filter = ('budget_tier', 'style', 'is_favorited')
    search_fields = ('name', 'style', 'project__title')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('contact_name', 'contact_phone', 'project', 'scheme', 'city', 'status', 'created_at')
    list_filter = ('status', 'city')
    search_fields = ('contact_name', 'contact_phone', 'project__title')


@admin.register(CustomerRequirement)
class CustomerRequirementAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'city', 'community', 'room_type', 'style',
                    'budget_min', 'budget_max', 'status', 'created_at')
    list_filter = ('status', 'city', 'room_type', 'style')
    search_fields = ('name', 'phone', 'community', 'requirement')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'city', 'rating', 'quote_range', 'is_active')
    list_filter = ('kind', 'city', 'is_active')
    search_fields = ('name', 'city', 'qualification')


@admin.register(Designer)
class DesignerAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'city', 'years', 'rating', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name', 'title', 'city')


@admin.register(Furniture)
class FurnitureAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'brand', 'style', 'rooms', 'price', 'buy_url', 'is_active')
    list_filter = ('category', 'style', 'is_active')
    search_fields = ('name', 'brand', 'model', 'supplier')


@admin.register(RenderJob)
class RenderJobAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'project', 'style', 'room_type', 'status', 'workflow',
                    'contractor', 'designer', 'created_at')
    list_filter = ('status', 'style', 'workflow')
    search_fields = ('project__title',)
    filter_horizontal = ('furnitures', 'prompt_modules')
    readonly_fields = ('prompt', 'negative_prompt', 'error', 'status', 'workflow_trace')

    @admin.display(description='工作流执行轨迹')
    def workflow_trace(self, obj):
        """把 workflow_log 渲染成可读的步骤轨迹，便于排查每一步的耗时与降级。"""
        from django.utils.html import format_html, format_html_join

        log = obj.workflow_log or []
        if not log:
            return '—'
        icons = {'ok': '✅', 'failed': '❌', 'skipped': '⏭'}
        rows = format_html_join(
            '', '<li>{} <b>{}</b> · {} <span style="color:#888">({}ms)</span></li>',
            ((icons.get(item.get('status'), '•'), item.get('name', ''),
              item.get('detail', ''), item.get('elapsed_ms', 0)) for item in log),
        )
        return format_html('<ol style="margin:0;padding-left:18px">{}</ol>', rows)


class WorkflowStepInline(admin.TabularInline):
    """在工作流页面里直接编排步骤：调顺序、开关、改参数。"""

    model = WorkflowStep
    extra = 1
    fields = ('order', 'kind', 'name', 'params', 'is_active', 'continue_on_error')
    ordering = ('order', 'id')
    verbose_name_plural = (
        '工作流步骤（params 常用键：'
        '缩放 {"max_side":1536}；增强/调色 {"brightness":1.08,"contrast":1.12,'
        '"saturation":1.05,"sharpness":1.15}；匹配家具 {"limit":6}；'
        '装配提示词 {"use_image_analysis":true}；追加提示词 {"positive":"","negative":""}；'
        '图生图 {"preserve_space":true,"fallback_to_text2img":true,"max_side":1024}；'
        '水印 {"text":"AI 效果图 · 仅供参考","position":"bottom_right","opacity":0.45}）'
    )


@admin.register(RenderWorkflow)
class RenderWorkflowAdmin(admin.ModelAdmin):
    list_display = ('name', 'step_count', 'is_default', 'is_active', 'stop_on_error', 'updated_at')
    list_filter = ('is_default', 'is_active')
    search_fields = ('name', 'description')
    inlines = (WorkflowStepInline,)
    fieldsets = (
        ('基础', {'fields': ('name', 'description')}),
        ('生效控制', {
            'fields': ('is_default', 'is_active', 'stop_on_error'),
            'description': (
                '默认工作流唯一：勾选后其他工作流会自动取消默认。'
                '任务未指定工作流时使用默认工作流；没有默认工作流则走内置最简链路。'
            ),
        }),
    )

    @admin.display(description='步骤数')
    def step_count(self, obj):
        return obj.steps.filter(is_active=True).count()


@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'order', 'kind', 'name', 'is_active', 'continue_on_error')
    list_filter = ('workflow', 'kind', 'is_active')
    list_editable = ('order', 'is_active', 'continue_on_error')
    search_fields = ('name',)


@admin.register(PromptModule)
class PromptModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'group', 'weight', 'is_default', 'is_active')
    list_filter = ('group', 'is_default', 'is_active')
    search_fields = ('code', 'name', 'prompt_fragment')
    list_editable = ('weight', 'is_default', 'is_active')
    fieldsets = (
        ('基础', {'fields': ('code', 'name', 'group', 'description')}),
        ('提示词', {
            'fields': ('prompt_fragment', 'negative_fragment', 'note_fragment'),
            'description': '提示词仅后端可见，前端只提交模块 code。',
        }),
        ('生效范围', {
            'fields': ('weight', 'is_default', 'is_active',
                       'applies_to_room_types', 'applies_to_styles'),
        }),
    )


@admin.register(GenerationConfig)
class GenerationConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'model', 'api_base', 'enabled', 'updated_at')
    fieldsets = (
        ('效果图生成（图像端点）', {
            'fields': ('image_enabled', 'image_provider', 'image_api_base',
                       'image_api_key', 'image_model', 'image_size'),
            'description': 'Pollinations 免费无需 Key：provider=pollinations，base=https://image.pollinations.ai，model=flux。',
        }),
        ('设计说明（文本大模型，可选）', {
            'fields': ('enabled', 'api_base', 'api_key', 'model'),
            'description': 'DeepSeek：base=https://api.deepseek.com/v1，model=deepseek-chat，需填 API Key。',
        }),
        ('基础', {'fields': ('name',)}),
        ('提示词', {'fields': ('prompt_template',)}),
    )

    def has_add_permission(self, request):
        # 单例：已存在则不允许新增
        return not GenerationConfig.objects.exists()


@admin.register(HomeReport)
class HomeReportAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'project', 'room_type', 'style', 'status', 'created_at')
    list_filter = ('status', 'style')
    search_fields = ('title', 'user__username', 'project__title')
    readonly_fields = ('report', 'created_at', 'updated_at')


@admin.register(HomeOrder)
class HomeOrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_no', 'customer_name', 'customer_phone', 'user', 'project',
        'total_amount', 'status', 'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'order_no', 'title', 'customer_name', 'customer_phone',
        'user__username', 'project__title',
    )
    readonly_fields = ('order_no', 'payload', 'created_at', 'updated_at')
    actions = ('sync_order_details',)
    fieldsets = (
        ('客户信息', {'fields': ('customer_name', 'customer_phone', 'user')}),
        ('关联项目', {'fields': ('project', 'report', 'title')}),
        ('订单金额', {'fields': ('amount_min', 'amount_max', 'total_amount')}),
        ('订单明细', {'fields': ('items', 'remark', 'payload')}),
        ('状态', {'fields': ('status', 'order_no')}),
    )

    @admin.action(description='同步选中订单的「订单详情」')
    def sync_order_details(self, request, queryset):
        for order in queryset:
            OrderDetail.sync_from_order(order)
        self.message_user(request, f'已同步 {queryset.count()} 条订单详情。')


@admin.register(OrderDetail)
class OrderDetailAdmin(admin.ModelAdmin):
    list_display = (
        'order_link', 'customer_name', 'customer_phone', 'project_title',
        'customer_image_count', 'generated_image_count', 'furniture_count',
        'designer_name', 'contractor_name', 'created_at',
    )
    list_filter = ('created_at', 'order__status')
    search_fields = (
        'order__order_no', 'order__customer_name', 'order__customer_phone',
        'order__project__title', 'order__report__title',
    )
    readonly_fields = (
        'order', 'customer_summary', 'customer_images_preview',
        'generated_images_preview', 'furniture_selection',
        'designer_summary', 'contractor_summary', 'created_at', 'updated_at',
    )
    fieldsets = (
        ('订单信息', {
            'fields': ('order', 'customer_summary', 'created_at', 'updated_at'),
        }),
        ('客户上传图片', {
            'fields': ('customer_images_preview', 'customer_images'),
            'description': '下单时自动同步户型图与客户上传的原始照片。',
        }),
        ('AI 生成图片', {
            'fields': ('generated_images_preview', 'generated_images'),
            'description': '下单时自动同步效果图任务生成的效果图。',
        }),
        ('家装建议', {'fields': ('design_advice',)}),
        ('家具选择', {
            'fields': ('furniture_selection', 'furniture_snapshot'),
            'description': '自动同步家具清单、价格、数量与购买链接。',
        }),
        ('设计师', {
            'fields': ('designer_summary', 'designer_snapshot'),
        }),
        ('装修队 / 服务商', {
            'fields': ('contractor_summary', 'contractor_snapshot'),
        }),
        ('前端报告快照', {'fields': ('report_snapshot',)}),
    )

    def _image_preview(self, images):
        images = [url for url in (images or []) if url]
        if not images:
            return '暂无图片'
        return format_html_join(
            '',
            '<div style="display:inline-block;margin:4px;vertical-align:top">'
            '<img src="{}" style="max-height:150px;max-width:240px;border-radius:6px" />'
            '<div style="font-size:11px;color:#888;word-break:break-all;max-width:240px">{}</div></div>',
            ((url, url) for url in images),
        )

    @admin.display(description='订单', ordering='order__order_no')
    def order_link(self, obj):
        url = reverse('admin:design_homeorder_change', args=[obj.order_id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_no or f'#{obj.order_id}')

    @admin.display(description='客户', ordering='order__customer_name')
    def customer_name(self, obj):
        return obj.order.customer_name or '-'

    @admin.display(description='电话', ordering='order__customer_phone')
    def customer_phone(self, obj):
        return obj.order.customer_phone or '-'

    @admin.display(description='项目', ordering='order__project__title')
    def project_title(self, obj):
        return obj.order.project.title if obj.order.project else '-'

    @admin.display(description='上传图数')
    def customer_image_count(self, obj):
        return len(obj.customer_images or [])

    @admin.display(description='生成图数')
    def generated_image_count(self, obj):
        return len(obj.generated_images or [])

    @admin.display(description='家具数')
    def furniture_count(self, obj):
        return len(obj.furniture_snapshot or [])

    @admin.display(description='设计师')
    def designer_name(self, obj):
        designer = obj.designer_snapshot or {}
        return designer.get('name') or '-'

    @admin.display(description='装修队')
    def contractor_name(self, obj):
        contractor = obj.contractor_snapshot or {}
        return contractor.get('name') or '-'

    @admin.display(description='客户摘要')
    def customer_summary(self, obj):
        order = obj.order
        designer = obj.designer_snapshot or {}
        parts = [
            f'客户：{order.customer_name or "-"}',
            f'电话：{order.customer_phone or "-"}',
            f'订单号：{order.order_no or "-"}',
            f'状态：{order.get_status_display()}',
            f'总价：¥{order.total_amount:,}' if order.total_amount else '总价：未填写',
            f'设计师：{designer.get("name") or "-"}',
        ]
        return format_html('<br>'.join('{}' for _ in parts), *parts)

    @admin.display(description='客户上传图片预览')
    def customer_images_preview(self, obj):
        return self._image_preview(obj.customer_images)

    @admin.display(description='AI 生成图片预览')
    def generated_images_preview(self, obj):
        return self._image_preview(obj.generated_images)

    @admin.display(description='家具选择预览')
    def furniture_selection(self, obj):
        items = obj.furniture_snapshot or []
        if not items:
            return '暂无家具'
        rows = []
        for item in items:
            name = item.get('name') or item.get('title') or '未命名'
            brand = item.get('brand') or ''
            category = item.get('category_display') or item.get('category') or ''
            price = item.get('price')
            quantity = item.get('quantity') or 1
            buy_url = item.get('buy_url')
            image_url = item.get('image_url')

            meta = ' · '.join(part for part in (brand, category) if part)
            meta_html = (
                format_html('<div style="color:#888;font-size:12px">{}</div>', meta)
                if meta
                else ''
            )
            price_text = f'¥{int(price):,}' if price is not None else '价格未填写'
            image_html = (
                format_html(
                    '<img src="{}" style="width:56px;height:56px;object-fit:cover;'
                    'border-radius:6px;margin-right:10px">',
                    image_url,
                )
                if image_url
                else ''
            )
            link_html = (
                format_html(
                    '<div style="font-size:12px;color:#0d6efd;word-break:break-all">'
                    '<a href="{}" target="_blank">{}</a></div>',
                    buy_url, buy_url,
                )
                if buy_url
                else format_html('<div style="font-size:12px;color:#999">暂无购买链接</div>')
            )
            rows.append(
                format_html(
                    '<div style="display:flex;align-items:center;padding:6px 0;'
                    'border-bottom:1px solid #eee">{}{}<div>'
                    '<b>{}</b>{}<div style="font-size:12px;color:#666">{} × {}</div>{}</div></div>',
                    image_html, name, meta_html, price_text, quantity, link_html,
                )
            )
        return format_html('<div style="margin-top:4px">{}</div>', mark_safe(''.join(rows)))

    @admin.display(description='设计师预览')
    def designer_summary(self, obj):
        designer = obj.designer_snapshot or {}
        if not designer:
            return '暂无设计师'
        parts = [
            f'{designer.get("name") or "-"} · {designer.get("title") or "-"}',
            f'城市：{designer.get("city") or "-"} · 从业 {designer.get("years") or 0} 年',
            f'擅长：{"、".join(designer.get("styles") or []) or "-"}',
            f'简介：{designer.get("intro") or "-"}',
        ]
        return format_html('<br>'.join('{}' for _ in parts), *parts)

    @admin.display(description='装修队/服务商预览')
    def contractor_summary(self, obj):
        contractor = obj.contractor_snapshot or {}
        if not contractor:
            return '暂无装修队/服务商'
        kind = contractor.get('kind_display') or contractor.get('kind') or '-'
        parts = [
            f'{contractor.get("name") or "-"} · {kind}',
            f'城市：{contractor.get("city") or "-"}',
            f'报价区间：{contractor.get("quote_range") or "-"}',
            f'响应速度：{contractor.get("response_speed") or "-"}',
        ]
        return format_html('<br>'.join('{}' for _ in parts), *parts)
