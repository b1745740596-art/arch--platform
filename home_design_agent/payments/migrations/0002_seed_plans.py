from django.db import migrations


PLANS = [
    {
        'name': '灵感包',
        'slug': 'starter',
        'credits': 10,
        'price_cents': 1990,
        'currency': 'CNY',
        'description': '适合偶尔生成灵感图',
        'sort_order': 10,
    },
    {
        'name': '进阶包',
        'slug': 'popular',
        'credits': 50,
        'price_cents': 7990,
        'currency': 'CNY',
        'description': '适合多空间比选',
        'sort_order': 20,
    },
    {
        'name': '专业包',
        'slug': 'value',
        'credits': 100,
        'price_cents': 13990,
        'currency': 'CNY',
        'description': '适合全屋多方案反复打磨',
        'sort_order': 30,
    },
]


def seed_plans(apps, schema_editor):
    PricingPlan = apps.get_model('payments', 'PricingPlan')
    for item in PLANS:
        PricingPlan.objects.update_or_create(slug=item['slug'], defaults=item)


def unseed_plans(apps, schema_editor):
    PricingPlan = apps.get_model('payments', 'PricingPlan')
    PricingPlan.objects.filter(slug__in=[p['slug'] for p in PLANS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]
