"""支付与额度模块测试。

覆盖：额度模型、充值下单/入账、幂等入账、营业额统计与权限控制。
运行方式：cd home_design_agent && .venv/bin/python manage.py test payments
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from payments.models import CreditTransaction, PaymentOrder, PricingPlan
from payments.services import (
    InsufficientCreditsError,
    balance_for_user,
    consume_generation_credit,
    mark_order_paid,
)

User = get_user_model()

PLANS_URL = '/api/payments/plans/'
BALANCE_URL = '/api/payments/balance/'
ORDERS_URL = '/api/payments/orders/'
ADMIN_STATS_URL = '/api/payments/admin/stats/'


class CreditServiceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='credit-user', password='secret123')

    def test_default_balance_is_five_free_credits(self):
        data = balance_for_user(self.user)
        self.assertEqual(data['free_credits'], 5)
        self.assertEqual(data['purchased_credits'], 0)
        self.assertEqual(data['total_credits'], 5)

    def test_consume_uses_free_then_purchased(self):
        consume_generation_credit(self.user, 3)
        balance = balance_for_user(self.user)
        self.assertEqual(balance['free_credits'], 2)
        self.assertEqual(balance['purchased_credits'], 0)

        plan = PricingPlan.objects.get(slug='starter')
        order = PaymentOrder.objects.create(
            user=self.user, plan=plan, provider='mock',
            amount_cents=plan.price_cents, currency=plan.currency, credits=plan.credits,
        )
        mark_order_paid(order)

        consume_generation_credit(self.user, 5)
        balance = balance_for_user(self.user)
        self.assertEqual(balance['free_credits'], 0)
        self.assertEqual(balance['purchased_credits'], 7)

    def test_insufficient_credits_raises(self):
        consume_generation_credit(self.user, 5)
        with self.assertRaises(InsufficientCreditsError):
            consume_generation_credit(self.user, 1)

    def test_mark_paid_is_idempotent(self):
        plan = PricingPlan.objects.get(slug='popular')
        order = PaymentOrder.objects.create(
            user=self.user, plan=plan, provider='mock',
            amount_cents=plan.price_cents, currency=plan.currency, credits=plan.credits,
        )
        mark_order_paid(order)
        mark_order_paid(order)
        balance = balance_for_user(self.user)
        self.assertEqual(balance['purchased_credits'], plan.credits)
        self.assertEqual(
            CreditTransaction.objects.filter(kind=CreditTransaction.Kind.PURCHASE).count(),
            1,
        )


class PaymentApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='secret123')
        self.client.force_authenticate(self.user)

    def test_list_plans_and_balance(self):
        plans = self.client.get(PLANS_URL)
        self.assertEqual(plans.status_code, status.HTTP_200_OK)
        self.assertEqual(len(plans.data), 3)

        balance = self.client.get(BALANCE_URL)
        self.assertEqual(balance.status_code, status.HTTP_200_OK)
        self.assertEqual(balance.data['total_credits'], 5)
        self.assertEqual(balance.data['payment_mode'], 'mock')

    def test_create_and_mock_pay_order(self):
        plan = PricingPlan.objects.get(slug='starter')
        created = self.client.post(ORDERS_URL, {'plan': plan.id, 'provider': 'stripe'}, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertTrue(created.data['payment']['mock'])

        order_id = created.data['order']['id']
        paid = self.client.post(f'{ORDERS_URL}{order_id}/mock_pay/')
        self.assertEqual(paid.status_code, status.HTTP_200_OK)
        self.assertEqual(paid.data['order']['status'], 'paid')
        self.assertEqual(paid.data['balance']['purchased_credits'], plan.credits)

    def test_orders_list_returns_only_own_orders(self):
        plan = PricingPlan.objects.get(slug='starter')
        other = User.objects.create_user(username='other', password='secret123')
        PaymentOrder.objects.create(
            user=other, plan=plan, provider='stripe',
            amount_cents=plan.price_cents, currency=plan.currency, credits=plan.credits,
        )
        response = self.client.get(ORDERS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class AdminStatsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='customer', password='secret123')
        self.staff = User.objects.create_user(
            username='ops', password='secret123', is_staff=True,
        )

    def test_admin_stats_requires_staff(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(ADMIN_STATS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_stats_reports_revenue(self):
        plan = PricingPlan.objects.get(slug='value')
        order = PaymentOrder.objects.create(
            user=self.user, plan=plan, provider='alipay',
            amount_cents=plan.price_cents, currency=plan.currency, credits=plan.credits,
        )
        mark_order_paid(order, reference='alipay-trade-1')

        self.client.force_authenticate(self.staff)
        response = self.client.get(ADMIN_STATS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['paid_orders'], 1)
        self.assertEqual(
            response.data['total_revenue'][0]['amount_cents'],
            plan.price_cents,
        )
        self.assertEqual(response.data['by_provider'][0]['provider'], 'alipay')
        self.assertEqual(len(response.data['daily_revenue']), 14)


class AdminCreditTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='credit-user', password='secret123')
        self.staff = User.objects.create_user(
            username='credit-admin', password='secret123', is_staff=True,
        )
        self.url = f'/api/payments/admin/users/{self.user.pk}/credits/'
        self.adjust_url = f'/api/payments/admin/users/{self.user.pk}/credits/adjust/'

    def test_requires_staff(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {'free_credits': 3}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_set_credits(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            self.url,
            {'free_credits': 3, 'purchased_credits': 12, 'note': '测试设置'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['free_credits'], 3)
        self.assertEqual(response.data['purchased_credits'], 12)
        self.assertTrue(
            CreditTransaction.objects.filter(
                user=self.user, kind=CreditTransaction.Kind.ADJUST,
            ).exists()
        )

    def test_adjust_credits(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            self.adjust_url,
            {'free_delta': -2, 'purchased_delta': 6},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['free_credits'], 3)
        self.assertEqual(response.data['purchased_credits'], 6)
        self.assertEqual(response.data['total_credits'], 9)

    def test_adjust_rejects_negative_balance(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            self.adjust_url,
            {'free_delta': -99},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
