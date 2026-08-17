from django.contrib import admin

from .models import CreditTransaction, PaymentOrder, PricingPlan


@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'credits', 'price', 'currency', 'sort_order', 'is_active')
    list_filter = ('currency', 'is_active')
    search_fields = ('name', 'slug', 'description')
    list_editable = ('sort_order', 'is_active')


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_no', 'user', 'plan', 'provider', 'status',
        'amount', 'currency', 'credits', 'paid_at', 'created_at',
    )
    list_filter = ('provider', 'status', 'currency')
    search_fields = ('order_no', 'user__username', 'user__email', 'provider_reference')
    readonly_fields = ('order_no', 'provider_response', 'paid_at', 'created_at', 'updated_at')
    raw_id_fields = ('user', 'plan')


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'credits', 'balance_after', 'note', 'created_at')
    list_filter = ('kind',)
    search_fields = ('user__username', 'user__email', 'note')
    raw_id_fields = ('user', 'order')
