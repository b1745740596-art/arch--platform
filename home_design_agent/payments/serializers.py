from rest_framework import serializers

from .models import CreditTransaction, PaymentOrder, PricingPlan


class PricingPlanSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = PricingPlan
        fields = (
            'id', 'name', 'slug', 'credits', 'price_cents', 'price',
            'currency', 'description', 'sort_order',
        )

    def get_price(self, obj):
        return obj.price


class PaymentOrderSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    plan = PricingPlanSerializer(read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = PaymentOrder
        fields = (
            'id', 'order_no', 'plan', 'provider', 'provider_display', 'status',
            'status_display', 'amount_cents', 'amount', 'currency', 'credits',
            'provider_reference', 'payment_note', 'provider_response', 'paid_at', 'created_at',
        )
        read_only_fields = fields

    def get_amount(self, obj):
        return obj.amount_cents / 100


class CreatePaymentOrderSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=PricingPlan.objects.filter(is_active=True))
    provider = serializers.ChoiceField(choices=PaymentOrder.Provider.choices)


class CreditTransactionSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = CreditTransaction
        fields = ('id', 'kind', 'kind_display', 'credits', 'balance_after', 'note', 'created_at')


class AdminPaymentOrderSerializer(PaymentOrderSerializer):
    """后台收款列表：额外附带下单用户信息。"""

    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta(PaymentOrderSerializer.Meta):
        fields = PaymentOrderSerializer.Meta.fields + ('username', 'user_email')
