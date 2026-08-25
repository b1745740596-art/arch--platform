from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from talkbot.engine import _persist_recovery_reply
from talkbot.models import Conversation, Message


class Command(BaseCommand):
    help = '恢复服务重启时遗留的 TalkBot 用户消息，并清理失效处理租约。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-age-minutes',
            type=int,
            default=10080,
            help='仅恢复最近多少分钟内的孤立消息，默认 7 天。',
        )

    def handle(self, *args, **options):
        max_age_minutes = max(1, options['max_age_minutes'])
        cutoff = timezone.now() - timedelta(minutes=max_age_minutes)
        cleared = Conversation.objects.filter(is_processing=True).update(
            is_processing=False,
            processing_started_at=None,
        )
        recovered = 0
        candidates = Conversation.objects.filter(
            status=Conversation.Status.ACTIVE,
            updated_at__gte=cutoff,
        ).only('id').order_by('id')
        for conversation in candidates.iterator():
            latest = conversation.messages.order_by('-id').first()
            if (
                latest is None
                or latest.role != Message.Role.USER
                or not latest.client_id
            ):
                continue
            if conversation.messages.filter(
                role=Message.Role.ASSISTANT,
                client_id=latest.client_id,
            ).exists():
                continue
            reply = _persist_recovery_reply(
                conversation.id,
                latest.client_id,
                error_type='WorkerRestart',
            )
            recovered += int(reply is not None)
        self.stdout.write(
            self.style.SUCCESS(f'租约清理={cleared}，中断轮次恢复={recovered}')
        )
