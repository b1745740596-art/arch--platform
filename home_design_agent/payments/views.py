from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsActiveUser

from .models import CreditTransaction, PaymentOrder, PricingPlan
from .serializers import (
    AdminPaymentOrderSerializer,
    CreatePaymentOrderSerializer,
    CreditTransactionSerializer,
    PaymentOrderSerializer,
    PricingPlanSerializer,
)
from .services import (
    balance_for_user,
    create_payment_order,
    get_admin_stats,
    get_payment_diagnostics,
    mark_order_paid,
    resolve_webhook,
)


class IsStaffOrSuperuser(IsAuthenticated):
    message = '仅后台人员可访问。'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.is_staff or request.user.is_superuser


class PlanListView(APIView):
    """可用充值套餐。"""

    permission_classes = [IsAuthenticated, IsActiveUser]

    def get(self, request):
        plans = PricingPlan.objects.filter(is_active=True).order_by('sort_order', 'id')
        return Response(PricingPlanSerializer(plans, many=True).data)


class BalanceView(APIView):
    """当前用户额度。"""

    permission_classes = [IsAuthenticated, IsActiveUser]

    def get(self, request):
        return Response(balance_for_user(request.user))


class TransactionListView(APIView):
    """当前用户额度流水。"""

    permission_classes = [IsAuthenticated, IsActiveUser]

    def get(self, request):
        transactions = CreditTransaction.objects.filter(user=request.user)[:100]
        return Response(CreditTransactionSerializer(transactions, many=True).data)


class PaymentOrderViewSet(viewsets.GenericViewSet):
    """用户支付订单：创建、查询与（仅 mock 模式）模拟支付。"""

    permission_classes = [IsAuthenticated, IsActiveUser]
    serializer_class = PaymentOrderSerializer

    def get_queryset(self):
        return PaymentOrder.objects.filter(user=self.request.user).select_related('plan')

    def list(self, request):
        orders = self.get_queryset()
        return Response(self.get_serializer(orders, many=True).data)

    def retrieve(self, request, pk=None):
        order = self.get_object()
        return Response(self.get_serializer(order).data)

    def create(self, request):
        serializer = CreatePaymentOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data['plan']
        provider = serializer.validated_data['provider']
        order, payload = create_payment_order(request.user, plan, provider, request)
        data = {
            'order': self.get_serializer(order).data,
            'payment': payload,
            'balance': balance_for_user(request.user),
        }
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def mock_pay(self, request, pk=None):
        """本地联调：模拟支付成功，仅在 PAYMENT_MODE=mock 时开放。"""
        if settings.PAYMENT_MODE == 'live':
            raise NotFound()
        order = self.get_object()
        order = mark_order_paid(order, reference=f'mock-{order.order_no}')
        return Response({
            'order': self.get_serializer(order).data,
            'balance': balance_for_user(request.user),
        })

    @action(detail=True, methods=['post'])
    def submit_proof(self, request, pk=None):
        """静态收款码模式：用户提交支付流水/联系方式，等待后台人工确认。"""
        order = self.get_object()
        if order.status != PaymentOrder.Status.PENDING:
            raise ValidationError('当前订单状态不能提交支付凭证。')
        note = (request.data.get('payment_note') or request.data.get('note') or '').strip()
        if not note:
            raise ValidationError('请填写支付流水号或联系方式。')
        if len(note) > 200:
            raise ValidationError('支付备注不能超过 200 个字符。')
        order.payment_note = note
        order.save(update_fields=['payment_note', 'updated_at'])
        return Response(self.get_serializer(order).data)


class AdminOrderListView(APIView):
    """收款列表：后台查看全部支付订单，可按状态/渠道筛选。"""

    permission_classes = [IsStaffOrSuperuser]

    def get(self, request):
        orders = PaymentOrder.objects.select_related('user', 'plan')
        status_filter = request.query_params.get('status')
        provider_filter = request.query_params.get('provider')
        if status_filter:
            orders = orders.filter(status=status_filter)
        if provider_filter:
            orders = orders.filter(provider=provider_filter)
        return Response(AdminPaymentOrderSerializer(orders[:200], many=True).data)


class AdminStatsView(APIView):
    """营业额展示：总营业额、今日/本月营业额与渠道拆分。"""

    permission_classes = [IsStaffOrSuperuser]

    def get(self, request):
        return Response(get_admin_stats())


class AdminDiagnosticsView(APIView):
    """支付链路自检：检查运行模式、依赖与渠道密钥配置，供上线前排查。"""

    permission_classes = [IsStaffOrSuperuser]

    def get(self, request):
        return Response(get_payment_diagnostics(request))


class AdminMarkPaidView(APIView):
    """后台人工确认收款。"""

    permission_classes = [IsStaffOrSuperuser]

    def post(self, request, pk):
        order = PaymentOrder.objects.filter(pk=pk).first()
        if order is None:
            raise NotFound('订单不存在。')
        if order.status == PaymentOrder.Status.PAID:
            raise ValidationError('该订单已支付。')
        order = mark_order_paid(order, reference=request.data.get('reference', '') or 'manual')
        return Response(PaymentOrderSerializer(order).data)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def stripe_webhook(request):
    try:
        order, handled, success = resolve_webhook('stripe', request)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    return Response({'received': True})


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def wechat_webhook(request):
    try:
        order, handled, success = resolve_webhook('wechat', request)
    except ValueError as exc:
        return Response({'code': 'FAIL', 'message': str(exc)}, status=400)
    if success:
        return Response({'code': 'SUCCESS', 'message': '成功'})
    return Response({'code': 'SUCCESS', 'message': '已收到'}, status=200)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def alipay_webhook(request):
    try:
        order, handled, success = resolve_webhook('alipay', request)
    except ValueError:
        return Response('failure', content_type='text/plain', status=400)
    return Response('success', content_type='text/plain')
