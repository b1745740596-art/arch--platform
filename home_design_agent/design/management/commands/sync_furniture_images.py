from django.core.management.base import BaseCommand
from django.db.models import Q

from design.imagegen import ensure_furniture_image
from design.models import Furniture, GenerationConfig


class Command(BaseCommand):
    help = '为家具商品补齐商品图（已有图默认跳过，--force 重新生成）'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='清空现有图片后重新生成')
        parser.add_argument('--limit', type=int, default=0, help='最多处理多少条，0 为不限制')

    def handle(self, *args, **options):
        config = GenerationConfig.load()
        qs = Furniture.objects.filter(is_active=True)
        if not options['force']:
            # 新建记录的 image 可能是 '' 或 NULL，两种都视为缺图
            qs = qs.filter(Q(image='') | Q(image__isnull=True))
        if options['limit']:
            qs = qs[:options['limit']]

        done = 0
        for furniture in qs:
            if options['force'] and furniture.image:
                furniture.image.delete(save=True)
            ensure_furniture_image(furniture, config)
            done += 1
            self.stdout.write(f'{furniture.name} → {furniture.image.name}')

        self.stdout.write(self.style.SUCCESS(
            f'furniture images ready: {done} processed, '
            f'image_enabled={config.image_enabled}'
        ))
