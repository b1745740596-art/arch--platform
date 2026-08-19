from django.core.management.base import BaseCommand

from design.models import Designer, Furniture, GenerationConfig, ServiceProvider


# (名称, 品类, 风格, 品牌, 参考价, 购买链接, 适用空间)
# 适用空间为空列表表示不限空间；图生图时按此过滤，避免客厅出现衣柜这类错配
FURNITURES = [
    ('北欧布艺三人沙发', 'sofa', '现代简约', 'IKEA', 4299, 'https://example.com/sofa-1',
     ['客厅', '书房']),
    ('意式极简真皮沙发', 'sofa', '意式极简', 'Natuzzi', 18800, 'https://example.com/sofa-2',
     ['客厅']),
    ('实木高箱储物床 1.8m', 'bed', '现代简约', '源氏木语', 3699, 'https://example.com/bed-1',
     ['主卧', '次卧']),
    ('岩板伸缩餐桌', 'table', '现代轻奢', '顾家家居', 5299, 'https://example.com/table-1',
     ['餐厅', '厨房']),
    ('全屋定制整墙衣柜', 'cabinet', '现代简约', '欧派', 12800, 'https://example.com/cab-1',
     ['主卧', '次卧']),
    ('极简线性吊灯', 'light', '意式极简', 'Nordic', 1299, 'https://example.com/light-1',
     ['客厅', '餐厅', '主卧', '次卧', '书房']),
    ('风冷十字对开门冰箱', 'appliance', '现代轻奢', '海尔', 4599, 'https://example.com/fridge-1',
     ['厨房']),
    ('通体大理石纹地砖 800x800', 'material', '现代轻奢', '马可波罗', 89,
     'https://example.com/tile-1', []),
    ('轻奢金属落地灯', 'light', '现代轻奢', '雷士', 899, 'https://example.com/light-2',
     ['客厅', '主卧', '次卧', '书房']),
    ('原木电视柜', 'cabinet', '现代简约', '源氏木语', 2199, 'https://example.com/cab-2',
     ['客厅']),
    ('棉麻窗帘定制', 'decor', '现代简约', '摩力克', 699, 'https://example.com/decor-1', []),
    ('意式极简餐边柜', 'cabinet', '意式极简', 'Natuzzi', 7999, 'https://example.com/cab-3',
     ['餐厅', '厨房']),
    ('实木书桌 1.4m', 'table', '现代简约', '源氏木语', 2599, 'https://example.com/table-2',
     ['书房', '次卧']),
    ('步入式衣帽间收纳柜', 'cabinet', '现代简约', '索菲亚', 16800, 'https://example.com/cab-5',
     ['衣帽间']),
    ('衣帽间化妆台带镜', 'table', '现代轻奢', '欧派', 4699, 'https://example.com/table-3',
     ['衣帽间']),
    ('衣帽间LED轨道灯', 'light', '现代简约', '欧普', 599, 'https://example.com/light-3',
     ['衣帽间']),
    ('嵌入式浴室镜柜', 'cabinet', '现代简约', '箭牌', 1899, 'https://example.com/cab-4',
     ['卫生间']),
    ('壁挂式智能马桶', 'appliance', '现代简约', '科勒', 5999, 'https://example.com/app-1',
     ['卫生间']),
]

DESIGNERS = [
    ('林岚', '主创设计师', '北京', ['现代简约', '现代轻奢'], 8, 4.9, '擅长小户型空间优化与收纳。'),
    ('陈默', '资深设计师', '上海', ['意式极简', '现代轻奢'], 12, 4.8, '意式极简风格代表，注重材质与光影。'),
    ('苏晴', '设计师', '深圳', ['现代简约', '北欧'], 5, 4.7, '年轻家庭首选，性价比与实用并重。'),
]

CONTRACTORS = [
    ('匠心装饰施工队', '北京', 4.8, '8万-20万', '2小时内响应'),
    ('精工装修工程', '上海', 4.7, '10万-30万', '当天响应'),
    ('鲁班施工联盟', '深圳', 4.6, '6万-18万', '4小时内响应'),
]


class Command(BaseCommand):
    help = '填充家具/设计师/施工队示例数据，并初始化生成配置'

    def handle(self, *args, **options):
        for name, cat, style, brand, price, url, rooms in FURNITURES:
            furniture, created = Furniture.objects.get_or_create(
                name=name,
                defaults=dict(category=cat, style=style, brand=brand, price=price,
                              buy_url=url, rooms=rooms),
            )
            # 已存在的记录补齐适用空间（旧数据没有该字段）
            if not created and not furniture.rooms and rooms:
                furniture.rooms = rooms
                furniture.save(update_fields=['rooms', 'updated_at'])
        for name, title, city, styles, years, rating, intro in DESIGNERS:
            Designer.objects.get_or_create(
                name=name,
                defaults=dict(title=title, city=city, styles=styles, years=years, rating=rating, intro=intro),
            )
        for name, city, rating, quote, speed in CONTRACTORS:
            ServiceProvider.objects.get_or_create(
                name=name,
                defaults=dict(
                    kind=ServiceProvider.Kind.CONSTRUCTION, city=city,
                    rating=rating, quote_range=quote, response_speed=speed,
                ),
            )
        GenerationConfig.load()
        self.stdout.write(self.style.SUCCESS(
            f'seed done: furniture={Furniture.objects.count()} '
            f'designers={Designer.objects.count()} '
            f'contractors={ServiceProvider.objects.filter(kind="construction").count()}'
        ))
