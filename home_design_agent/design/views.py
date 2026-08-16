import django
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import (
    CustomerRequirement,
    Designer,
    DesignScheme,
    Furniture,
    Lead,
    Owner,
    Project,
    RenderWorkflow,
    RenderJob,
    ServiceProvider,
)
from .serializers import (
    CustomerRequirementSerializer,
    DesignerSerializer,
    DesignSchemeSerializer,
    FurnitureSerializer,
    LeadSerializer,
    LoginSerializer,
    OwnerSerializer,
    ProjectListSerializer,
    ProjectSerializer,
    RegisterSerializer,
    RenderJobSerializer,
    RenderWorkflowSerializer,
    ServiceProviderSerializer,
)
from .imagegen import run_render_job
from .prompts import option_payload, suggest_variants
from .services import build_preview_schemes


@api_view(['GET'])
def health(request):
    """环境自检端点，用于确认 Django 与 DRF 已正确装配。"""
    return Response({
        'status': 'ok',
        'app': 'design',
        'django': django.get_version(),
    })


def _user_payload(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }


@api_view(['POST'])
def register_user(request):
    """用户端注册：只创建普通用户，`is_staff/is_superuser` 均为 False。"""
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(_user_payload(user), status=201)


@api_view(['POST'])
def login_user(request):
    """用户端登录：使用 Django Session 登录，后台访问仍受 is_staff 限制。"""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    username = serializer.validated_data['username']
    password = serializer.validated_data['password']
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'detail': '用户名或密码错误。'}, status=400)
    login(request, user)
    return Response(_user_payload(user))


@api_view(['POST'])
def logout_user(request):
    """用户端退出登录。"""
    logout(request)
    return Response({'detail': '已退出登录。'})


@api_view(['GET'])
def current_user(request):
    """返回当前登录用户；未登录返回 401。"""
    if not request.user.is_authenticated:
        return Response({'detail': '未登录。'}, status=401)
    return Response(_user_payload(request.user))


@api_view(['GET'])
def prompt_module_options(request):
    """下发前端可选项与输入约束（枚举、控制模块、图片/文本限制）。

    前端的严格约束以此为唯一口径，后端在序列化器里做同口径二次校验。
    """
    return Response(option_payload(
        room_type=request.query_params.get('room_type', ''),
        style=request.query_params.get('style', ''),
    ))


@api_view(['GET'])
def prompt_module_suggest(request):
    """发散选项：给出多套控制模块组合，供一键套用或分别开窗并行生成。"""
    return Response({'variants': suggest_variants(
        room_type=request.query_params.get('room_type', ''),
        style=request.query_params.get('style', ''),
        budget_tier=request.query_params.get('budget_tier', ''),
    )})


class OwnerViewSet(viewsets.ModelViewSet):
    queryset = Owner.objects.all()
    serializer_class = OwnerSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.prefetch_related('schemes').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        return ProjectSerializer

    @action(detail=True, methods=['post'])
    def generate_schemes(self, request, pk=None):
        """生成 ≥3 套预方案（PRD 5.3）。当前为规则生成，后续可替换为 LLM。"""
        project = self.get_object()
        project.schemes.all().delete()
        created = build_preview_schemes(project)
        project.status = Project.Status.SCHEME
        project.save(update_fields=['status', 'updated_at'])
        return Response(DesignSchemeSerializer(created, many=True).data)


class DesignSchemeViewSet(viewsets.ModelViewSet):
    queryset = DesignScheme.objects.select_related('project').all()
    serializer_class = DesignSchemeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request, pk=None):
        scheme = self.get_object()
        scheme.is_favorited = not scheme.is_favorited
        scheme.save(update_fields=['is_favorited', 'updated_at'])
        return Response(self.get_serializer(scheme).data)


class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.select_related('project', 'scheme').all()
    serializer_class = LeadSerializer

    def perform_create(self, serializer):
        lead = serializer.save()
        # 留资后推进项目状态（PRD 5.5 线索转化）
        project = lead.project
        if project.status not in (Project.Status.SIGNED,):
            project.status = Project.Status.LEAD
            project.save(update_fields=['status', 'updated_at'])


class CustomerRequirementViewSet(viewsets.ModelViewSet):
    """用户需求收集：前台可提交，运营在后台跟进。

    用户侧只允许创建与查询自己的提交结果；这里按 MVP 简化为公开创建接口，
    状态字段只读，避免用户伪造跟进状态。
    """

    queryset = CustomerRequirement.objects.all()
    serializer_class = CustomerRequirementSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        """需求提交后同步到业主、项目与留资线索，方便后台统一跟进。"""
        requirement = serializer.save()

        owner, owner_created = Owner.objects.get_or_create(
            phone=requirement.phone,
            defaults={
                'name': requirement.name,
                'city': requirement.city,
                'community': requirement.community,
            },
        )
        if not owner_created:
            owner.name = requirement.name or owner.name
            owner.city = requirement.city or owner.city
            owner.community = requirement.community or owner.community
            owner.save(update_fields=['name', 'city', 'community', 'updated_at'])

        owner.preference_tags = list(dict.fromkeys(
            [tag for tag in (requirement.room_type, requirement.style, '需求登记') if tag]
            + (owner.preference_tags or [])
        ))
        owner.save(update_fields=['preference_tags', 'updated_at'])

        project = Project.objects.create(
            owner=owner,
            title=f'{requirement.city or "未填写城市"}·{requirement.room_type or "装修需求"}',
            city=requirement.city,
            community=requirement.community,
            budget_min=requirement.budget_min,
            budget_max=requirement.budget_max,
            requirement_summary={
                'requirement': requirement.requirement,
                'room_type': requirement.room_type,
                'style': requirement.style,
            },
            status=Project.Status.REQUIREMENT,
        )

        Lead.objects.create(
            project=project,
            contact_name=requirement.name,
            contact_phone=requirement.phone,
            city=requirement.city,
            community=requirement.community,
            remark=requirement.requirement,
        )


class ServiceProviderViewSet(viewsets.ModelViewSet):
    queryset = ServiceProvider.objects.filter(is_active=True)
    serializer_class = ServiceProviderSerializer


class DesignerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Designer.objects.filter(is_active=True)
    serializer_class = DesignerSerializer


class FurnitureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Furniture.objects.filter(is_active=True)
    serializer_class = FurnitureSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        style = self.request.query_params.get('style')
        if category:
            qs = qs.filter(category=category)
        if style:
            qs = qs.filter(style=style)
        return qs


class RenderWorkflowViewSet(viewsets.ReadOnlyModelViewSet):
    """生图工作流（只读）：前端可展示可选流程，编排在 admin 完成。"""

    queryset = RenderWorkflow.objects.filter(is_active=True).prefetch_related('steps')
    serializer_class = RenderWorkflowSerializer


class RenderJobViewSet(viewsets.ModelViewSet):
    """效果图任务：上传毛坯照片 + 需求，创建后调用大模型生成。"""

    queryset = (
        RenderJob.objects
        .select_related('contractor', 'designer', 'workflow')
        .prefetch_related('furnitures', 'prompt_modules')
        .all()
    )
    serializer_class = RenderJobSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def perform_create(self, serializer):
        module_codes = serializer.validated_data.pop('module_codes', '')
        job = serializer.save()
        # 同步生成（占位或真实）。生产可改为异步队列。
        # module_codes 只是模块编码，真正的提示词由后端 prompt 控制模块提供。
        run_render_job(job, module_codes)

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        job = self.get_object()
        module_codes = request.data.get('module_codes')
        run_render_job(job, module_codes)
        return Response(self.get_serializer(job).data)
