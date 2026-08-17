import django
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    CustomerRequirement,
    Designer,
    DesignScheme,
    Furniture,
    HomeOrder,
    HomeReport,
    Lead,
    OrderDetail,
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
    HomeOrderSerializer,
    HomeReportSerializer,
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
from payments.services import consume_generation_credit, refund_generation_credit


@api_view(['GET'])
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
def register_user(request):
    """用户端注册：只创建普通用户，`is_staff/is_superuser` 均为 False。"""
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(_user_payload(user), status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
def logout_user(request):
    """用户端退出登录。"""
    logout(request)
    return Response({'detail': '已退出登录。'})


@api_view(['GET'])
@permission_classes([AllowAny])
def current_user(request):
    """返回当前登录用户；未登录返回 401。"""
    if not request.user.is_authenticated:
        return Response({'detail': '未登录。'}, status=401)
    return Response(_user_payload(request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def prompt_module_options(request):
    """下发前端可选项与输入约束（枚举、控制模块、图片/文本限制）。

    前端的严格约束以此为唯一口径，后端在序列化器里做同口径二次校验。
    """
    return Response(option_payload(
        room_type=request.query_params.get('room_type', ''),
        style=request.query_params.get('style', ''),
    ))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
    permission_classes = [IsAuthenticated]


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.prefetch_related('schemes').all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """普通用户只能访问自己名下项目，后台可看全部。"""
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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


class HomeReportViewSet(viewsets.ModelViewSet):
    """「我的家」报告书：一次成功输出 = 一份报告 = 一个用户项目。

    普通用户只能查看自己的报告；创建时自动把 user 与 project 绑定。
    """

    queryset = HomeReport.objects.select_related('project', 'render_job').all()
    serializer_class = HomeReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        report_data = data.get('report') or {}
        project = data.get('project')

        if project is None:
            title = (
                data.get('title')
                or report_data.get('title')
                or f'{data.get("room_type") or "空间"}·{data.get("style") or "方案"} 装修报告'
            )
            project = Project.objects.create(
                user=self.request.user,
                title=title,
                status=Project.Status.SCHEME,
            )
        elif project.user_id != self.request.user.id and not self.request.user.is_staff:
            raise PermissionDenied('不能把报告保存到其他用户的项目。')

        serializer.save(
            user=self.request.user,
            project=project,
            report=report_data,
        )


class HomeOrderViewSet(viewsets.ModelViewSet):
    """「我的家」项目订单：记录客户下单、订单明细、金额与状态流转。

    普通用户可创建订单并取消自己的待确认订单；确认、支付、完成由后台人员操作。
    """

    queryset = HomeOrder.objects.select_related('project', 'report').all()
    serializer_class = HomeOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def _ensure_staff(self):
        if not self.request.user.is_staff:
            raise PermissionDenied('仅后台人员可执行该操作。')

    def _ensure_order_owner_or_staff(self, order):
        if order.user_id != self.request.user.id and not self.request.user.is_staff:
            raise PermissionDenied('不能操作其他用户的订单。')

    def _transition(self, order, status):
        order.status = status
        order.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(order).data)

    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        report = data.get('report')
        project = data.get('project') or (report.project if report else None)

        if project is None:
            raise PermissionDenied('请先选择要下单的项目或报告。')
        if project.user_id != self.request.user.id and not self.request.user.is_staff:
            raise PermissionDenied('不能为其他用户的项目下单。')

        amount_min = data.get('amount_min')
        amount_max = data.get('amount_max')
        if (amount_min is None or amount_max is None) and report:
            amount_min = report.report.get('budget_min', amount_min)
            amount_max = report.report.get('budget_max', amount_max)

        items = data.get('items') or []
        if not items and report:
            items = [
                {
                    'name': item.get('name', ''),
                    'category': item.get('category_display', ''),
                    'price': item.get('price'),
                    'quantity': 1,
                    'amount': item.get('price'),
                }
                for item in (report.report.get('furnitures') or [])
            ]

        total_amount = data.get('total_amount')
        if total_amount is None and items:
            total_amount = sum(
                int(item.get('amount') or (int(item.get('price') or 0) * int(item.get('quantity') or 1)))
                for item in items
            )

        customer_name = (
            data.get('customer_name')
            or self.request.user.get_full_name().strip()
            or self.request.user.username
        )
        customer_phone = data.get('customer_phone') or ''
        title = data.get('title') or (report.title if report else project.title)

        order = serializer.save(
            user=self.request.user,
            project=project,
            report=report,
            title=title,
            customer_name=customer_name,
            customer_phone=customer_phone,
            items=items,
            amount_min=amount_min,
            amount_max=amount_max,
            total_amount=total_amount,
        )
        OrderDetail.sync_from_order(order)

        if report:
            report.status = HomeReport.Status.ORDERED
            report.save(update_fields=['status', 'updated_at'])
        project.status = Project.Status.SIGNED
        project.save(update_fields=['status', 'updated_at'])
        return order

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """用户可取消自己的待确认/已确认订单，后台人员可取消任何未完结订单。"""
        order = self.get_object()
        self._ensure_order_owner_or_staff(order)
        if order.status in (HomeOrder.Status.PAID, HomeOrder.Status.COMPLETED, HomeOrder.Status.CANCELLED):
            raise ValidationError('当前订单状态不能取消。')
        return self._transition(order, HomeOrder.Status.CANCELLED)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """后台确认订单。"""
        self._ensure_staff()
        order = self.get_object()
        if order.status != HomeOrder.Status.PENDING:
            raise ValidationError('仅待确认订单可执行确认。')
        return self._transition(order, HomeOrder.Status.CONFIRMED)

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """后台标记订单已支付。"""
        self._ensure_staff()
        order = self.get_object()
        if order.status not in (HomeOrder.Status.PENDING, HomeOrder.Status.CONFIRMED):
            raise ValidationError('仅待确认或已确认订单可标记为已支付。')
        return self._transition(order, HomeOrder.Status.PAID)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """后台标记订单已完成。"""
        self._ensure_staff()
        order = self.get_object()
        if order.status != HomeOrder.Status.PAID:
            raise ValidationError('仅已支付订单可标记为已完成。')
        return self._transition(order, HomeOrder.Status.COMPLETED)


class DesignSchemeViewSet(viewsets.ModelViewSet):
    queryset = DesignScheme.objects.select_related('project').all()
    serializer_class = DesignSchemeSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]


class DesignerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Designer.objects.filter(is_active=True)
    serializer_class = DesignerSerializer
    permission_classes = [IsAuthenticated]


class FurnitureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Furniture.objects.filter(is_active=True)
    serializer_class = FurnitureSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]


class RenderJobViewSet(viewsets.ModelViewSet):
    """效果图任务：上传毛坯照片 + 需求，创建后调用大模型生成。"""

    queryset = (
        RenderJob.objects
        .select_related('contractor', 'designer', 'workflow')
        .prefetch_related('furnitures', 'prompt_modules')
        .all()
    )
    serializer_class = RenderJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def perform_create(self, serializer):
        module_codes = serializer.validated_data.pop('module_codes', '')
        deduction = consume_generation_credit(self.request.user)
        job = None
        try:
            job = serializer.save()
            # 同步生成（占位或真实）。生产可改为异步队列。
            # module_codes 只是模块编码，真正的提示词由后端 prompt 控制模块提供。
            run_render_job(job, module_codes)
        except Exception:
            refund_generation_credit(
                self.request.user,
                deduction['free_used'],
                deduction['purchased_used'],
            )
            if job is not None:
                job.delete()
            raise

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        job = self.get_object()
        module_codes = request.data.get('module_codes')
        deduction = consume_generation_credit(request.user)
        try:
            run_render_job(job, module_codes)
        except Exception:
            refund_generation_credit(
                request.user,
                deduction['free_used'],
                deduction['purchased_used'],
            )
            raise
        return Response(self.get_serializer(job).data)
