from django.urls import path

from . import views

app_name = 'payments'

payment_order_list = views.PaymentOrderViewSet.as_view({'get': 'list', 'post': 'create'})
payment_order_detail = views.PaymentOrderViewSet.as_view({'get': 'retrieve'})
payment_order_mock_pay = views.PaymentOrderViewSet.as_view({'post': 'mock_pay'})
payment_order_submit_proof = views.PaymentOrderViewSet.as_view({'post': 'submit_proof'})

urlpatterns = [
    path('plans/', views.PlanListView.as_view(), name='plans'),
    path('balance/', views.BalanceView.as_view(), name='balance'),
    path('transactions/', views.TransactionListView.as_view(), name='transactions'),
    path('orders/', payment_order_list, name='order-list'),
    path('orders/<int:pk>/', payment_order_detail, name='order-detail'),
    path('orders/<int:pk>/mock_pay/', payment_order_mock_pay, name='order-mock-pay'),
    path('orders/<int:pk>/submit_proof/', payment_order_submit_proof, name='order-submit-proof'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe-webhook'),
    path('webhook/wechat/', views.wechat_webhook, name='wechat-webhook'),
    path('webhook/alipay/', views.alipay_webhook, name='alipay-webhook'),
    path('admin/orders/', views.AdminOrderListView.as_view(), name='admin-order-list'),
    path('admin/stats/', views.AdminStatsView.as_view(), name='admin-stats'),
    path('admin/diagnostics/', views.AdminDiagnosticsView.as_view(), name='admin-diagnostics'),
    path('admin/orders/<int:pk>/mark-paid/', views.AdminMarkPaidView.as_view(), name='admin-mark-paid'),
]
