"""把家具库扩充到 300 个条目的演示命令。

说明：
- 图片使用 LoremFlickr 的公开图片接口下载（按品类关键词 + lock 生成稳定图片），
  不直接爬取电商网站，避免违反目标站点服务条款。
- 购买链接使用电商平台的搜索链接，方便用户继续查看真实商品。
"""

import time
import urllib.parse
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from design.models import Furniture

GROUPS = [
    {
        'category': Furniture.Category.SOFA,
        'keyword': 'sofa,interior',
        'rooms': ['客厅'],
        'brands': ['顾家家居', '全友', '林氏木业', '宜家', '源氏木语'],
        'price_min': 1800, 'price_max': 12000,
        'styles': ['现代简约', '北欧', '轻奢'],
        'names': [
            '三人位布艺沙发', '三人位真皮沙发', '转角组合沙发', '单人休闲沙发',
            '双人位沙发', '科技布功能沙发', '意式极简沙发', '奶油风云朵沙发',
            '北欧原木沙发', '轻奢绒布沙发', '侘寂风沙发', '中式实木沙发',
            '日式榻榻米沙发', '儿童房沙发', '模块化组合沙发', '可躺电动沙发',
            'L型沙发', '高靠背沙发', '小户型双人沙发', '客厅大三人沙发',
        ],
    },
    {
        'category': Furniture.Category.BED,
        'keyword': 'bed,bedroom',
        'rooms': ['主卧', '次卧'],
        'brands': ['喜临门', '慕思', '顾家家居', '全友', '林氏木业'],
        'price_min': 2200, 'price_max': 15000,
        'styles': ['现代简约', '轻奢', '奶油风'],
        'names': [
            '实木双人床', '布艺软包床', '真皮软床', '现代简约床', '北欧实木床',
            '意式极简床', '奶油风床', '轻奢软床', '儿童高低床', '榻榻米床',
            '箱体储物床', '悬浮床', '中式实木床', '日式原木床', '铁艺床',
            '科技布软床', '主卧大床', '次卧单人床', '床尾凳床', '酒店风软包床',
        ],
    },
    {
        'category': Furniture.Category.TABLE,
        'keyword': 'table,furniture',
        'rooms': ['客厅', '餐厅', '书房'],
        'brands': ['林氏木业', '源氏木语', '全友', '顾家家居', '芝华仕'],
        'price_min': 500, 'price_max': 9000,
        'styles': ['现代简约', '北欧'],
        'names': [
            '岩板餐桌', '实木餐桌', '伸缩餐桌', '圆餐桌', '方形餐桌',
            '餐岛一体桌', '实木茶几', '岩板茶几', '玻璃茶几', '组合茶几',
            '边几', '床头柜', '书桌', '办公桌', '梳妆台',
            '吧台桌', '儿童学习桌', '折叠餐桌', '原木餐桌', '大理石餐桌',
            '多功能茶几', '小户型餐桌', '书桌组合', '餐桌椅套装', '茶桌椅',
        ],
    },
    {
        'category': Furniture.Category.CABINET,
        'keyword': 'cabinet,furniture',
        'rooms': ['客厅', '餐厅', '卧室', '衣帽间', '书房'],
        'brands': ['欧派', '索菲亚', '尚品宅配', '志邦', '好莱客'],
        'price_min': 600, 'price_max': 20000,
        'styles': ['现代简约', '原木'],
        'names': [
            '电视柜', '低矮电视柜', '实木电视柜', '岩板电视柜', '玄关柜',
            '鞋柜', '餐边柜', '酒柜', '书柜', '衣柜',
            '推拉门衣柜', '平开门衣柜', '衣帽间柜', '床头柜', '收纳柜',
            '展示柜', '斗柜', '五斗柜', '七斗柜', '储物柜',
            '阳台柜', '浴室柜', '厨房橱柜', '吊柜', '组合柜',
        ],
    },
    {
        'category': Furniture.Category.LIGHT,
        'keyword': 'lamp,lighting',
        'rooms': ['客厅', '餐厅', '主卧', '次卧', '衣帽间', '书房'],
        'brands': ['雷士', '欧普', '飞利浦', '松下', '月影'],
        'price_min': 150, 'price_max': 4000,
        'styles': ['现代简约', '北欧'],
        'names': [
            '客厅吊灯', '餐厅吊灯', '卧室吊灯', '北欧吊灯', '轻奢吊灯',
            '吸顶灯', '全屋吸顶灯', '现代吸顶灯', '落地灯', '北欧落地灯',
            '台灯', '护眼台灯', '壁灯', '床头壁灯', '射灯',
            '筒灯', '轨道灯', '氛围灯带', '水晶吊灯', '风扇灯',
        ],
    },
    {
        'category': Furniture.Category.APPLIANCE,
        'keyword': 'appliance,kitchen',
        'rooms': ['厨房', '客厅', '卫生间'],
        'brands': ['海尔', '美的', '格力', '西门子', '松下'],
        'price_min': 1200, 'price_max': 20000,
        'styles': ['现代简约', '智能'],
        'names': [
            '双开门冰箱', '十字门冰箱', '滚筒洗衣机', '洗烘一体机', '65寸电视',
            '75寸电视', '中央空调', '挂式空调', '油烟机', '燃气热水器',
        ],
    },
    {
        'category': Furniture.Category.MATERIAL,
        'keyword': 'tiles,flooring',
        'rooms': ['客厅', '厨房', '卫生间'],
        'brands': ['马可波罗', '东鹏', '大自然', '立邦', '多乐士'],
        'price_min': 80, 'price_max': 1200,
        'styles': ['现代简约'],
        'names': [
            '客厅地砖', '厨房墙砖', '卫生间瓷砖', '木地板', '实木复合地板',
            '乳胶漆', '艺术涂料', '壁纸', '集成吊顶', '实木踢脚线',
        ],
    },
    {
        'category': Furniture.Category.DECOR,
        'keyword': 'curtain,decor',
        'rooms': ['客厅', '卧室', '衣帽间', '书房'],
        'brands': ['宜家', 'ZARA HOME', '摩力克', '罗莱', '网易严选'],
        'price_min': 50, 'price_max': 1500,
        'styles': ['现代简约'],
        'names': [
            '客厅窗帘', '卧室窗帘', '地毯', '客厅地毯', '装饰画',
            '绿植', '仿真花', '抱枕', '落地镜', '挂钟',
        ],
    },
]


def _expand_group(group, target):
    items = []
    names = group['names']
    styles = group['styles']
    for index in range(target):
        base_name = names[index % len(names)]
        style = styles[(index // len(names)) % len(styles)]
        name = f'{style}{base_name}'
        price_min = group['price_min'] + (index * 173) % max(1, group['price_max'] - group['price_min'])
        price_max = min(group['price_max'], price_min + 2000 + (index * 137) % 5000)
        items.append({
            'name': name,
            'category': group['category'],
            'keyword': group['keyword'],
            'brand': group['brands'][index % len(group['brands'])],
            'style': style,
            'rooms': group['rooms'],
            'price_min': price_min,
            'price_max': price_max,
            'buy_query': name,
        })
    return items


def build_catalog(count):
    target = [60, 60, 50, 50, 40, 20, 10, 10]
    total = sum(target)
    if count and count < total:
        # 按品类比例压缩到目标数量
        scale = count / total
        target = [max(1, round(n * scale)) for n in target]
    catalog = []
    for group, n in zip(GROUPS, target):
        catalog.extend(_expand_group(group, n))
    return catalog


def _download_image(keyword, index):
    url = f'https://loremflickr.com/600/450/{urllib.parse.quote(keyword)}?lock={index}'
    req = urllib.request.Request(url, headers={'User-Agent': 'SmartWork/1.0'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if data and len(data) > 1000:
                return data
        except Exception:
            time.sleep(1 + attempt)
    return None


class Command(BaseCommand):
    help = '扩充家具库：创建指定数量的家具、灯具、建材/软装条目并下载演示图片。'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=300, help='目标新增条目数')
        parser.add_argument('--no-images', action='store_true', help='只创建数据，不下载图片')

    def handle(self, *args, **options):
        count = options['count']
        catalog = build_catalog(count)
        created = 0
        images = 0

        for index, item in enumerate(catalog):
            obj, was_created = Furniture.objects.update_or_create(
                name=item['name'],
                defaults={
                    'category': item['category'],
                    'brand': item['brand'],
                    'style': item['style'],
                    'rooms': item['rooms'],
                    'price': item['price_max'],
                    'buy_url': 'https://s.taobao.com/search?q=' + urllib.parse.quote(item['buy_query']),
                    'supplier': item['brand'],
                    'is_active': True,
                },
            )
            created += 1

            if not options['no_images'] and not obj.image:
                data = _download_image(item['keyword'], index)
                if data:
                    obj.image.save(
                        f"furniture_lib_{index}.jpg",
                        ContentFile(data),
                        save=True,
                    )
                    images += 1

            if (index + 1) % 50 == 0:
                self.stdout.write(f'进度：已处理 {index + 1}/{len(catalog)}，图片 {images} 张')

        self.stdout.write(self.style.SUCCESS(
            f'家具库扩充完成：处理 {created} 条，成功下载图片 {images} 张'
        ))
