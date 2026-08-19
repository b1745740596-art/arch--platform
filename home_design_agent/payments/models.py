import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class PricingPlan(models.Model):
    """充值套餐：一份套餐对应若干次生成额度与一个价格。"""

    CURRENCY_CNY = 'CNY'
    CURRENCY_USD = 'USD'
    CURRENCY_CHOICES = (
        (CURRENCY_CNY, '人民币'),
        (CURRENCY_USD, '美元'),
    )

    name = models.CharField('套餐名称', max_length=80)
    slug = models.SlugField('套餐编码', max_length=50, unique=True)
    credits = models.PositiveIntegerField('生成额度', help_text='购买后增加的生成次数')
    price_cents = models.PositiveIntegerField('价格（分）', help_text='以最小货币单位计，如 19.90 元存 1990')
    currency = models.CharField(
        '币种', max_length=3, choices=CURRENCY_CHOICES, default=CURRENCY_CNY,
    )
    description = models.CharField('套餐说明', max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField('排序', default=100)
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '充值套餐'
        ordering = ('sort_order', 'id')

    def __str__(self):
        return f'{self.name}（{self.credits} 次）'

    @property
    def price(self):
        return self.price_cents / 100


class PaymentOrder(models.Model):
    """支付订单：用户充值套餐时创建，支付成功后把额度计入用户账户。"""

    class Provider(models.TextChoices):
        STRIPE = 'stripe', 'Stripe'
        WECHAT = 'wechat', '微信支付'
        ALIPAY = 'alipay', '支付宝'

    class Status(models.TextChoices):
        PENDING = 'pending', '待支付'
        PAID = 'paid', '已支付'
        FAILED = 'failed', '支付失败'
        CANCELLED = 'cancelled', '已取消'
        REFUNDED = 'refunded', '已退款'

    order_no = models.CharField(
        '订单编号', max_length=40, unique=True, blank=True, editable=False,
        help_text='系统自动生成，如 PAY20260817123000A1B2C3',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='payment_orders', verbose_name='用户',
    )
    plan = models.ForeignKey(
        PricingPlan, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders', verbose_name='充值套餐',
    )
    provider = models.CharField('支付渠道', max_length=10, choices=Provider.choices)
    status = models.CharField('状态', max_length=12, choices=Status.choices, default=Status.PENDING)
    amount_cents = models.PositiveIntegerField('实付金额（分）')
    currency = models.CharField('币种', max_length=3, default=PricingPlan.CURRENCY_CNY)
    credits = models.PositiveIntegerField('购买额度', default=0)
    provider_reference = models.CharField(
        '渠道交易号', max_length=120, blank=True, db_index=True,
        help_text='如 Stripe Session ID / 微信 out_trade_no / 支付宝 trade_no',
    )
    payment_note = models.CharField(
        '支付备注', max_length=200, blank=True,
        help_text='静态收款码模式下，用户填写的支付流水/联系方式，供后台人工核对',
    )
    provider_response = models.JSONField('渠道响应', default=dict, blank=True)
    paid_at = models.DateTimeField('支付时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '收款订单'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.order_no or "支付订单"}（{self.get_status_display()}）'

    @property
    def amount(self):
        return self.amount_cents / 100

    def _generate_order_no(self):
        prefix = timezone.localtime().strftime('PAY%Y%m%d%H%M%S')
        suffix = uuid.uuid4().hex[:8].upper()
        return f'{prefix}{suffix}'

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = self._generate_order_no()
        super().save(*args, **kwargs)


class CreditTransaction(models.Model):
    """额度流水：记录免费额度发放、充值入账与生成消耗，用于对账与营业额统计。"""

    class Kind(models.TextChoices):
        GRANT = 'grant', '免费额度'
        PURCHASE = 'purchase', '充值入账'
        CONSUME = 'consume', '生成消耗'
        REFUND = 'refund', '失败退回'
        ADJUST = 'adjust', '管理员调整'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='credit_transactions', verbose_name='用户',
    )
    order = models.ForeignKey(
        PaymentOrder, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='credit_transactions', verbose_name='关联订单',
    )
    kind = models.CharField('流水类型', max_length=10, choices=Kind.choices)
    credits = models.IntegerField('额度变动', help_text='正数为入账，负数为消耗')
    balance_after = models.PositiveIntegerField('变动后总额度', default=0)
    note = models.CharField('备注', max_length=200, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '额度流水'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user} {self.get_kind_display()} {self.credits:+d}'
