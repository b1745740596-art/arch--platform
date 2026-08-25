from django.core.management.base import BaseCommand
from django.db import transaction

from talkbot.models import Conversation, CustomerProfile
from talkbot.profile_repair import replay_profile_scores


class Command(BaseCommand):
    help = '审计并可选修复 TalkBot 重试导致的信任度、意向度和情绪轨迹重复累加'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            '--apply',
            action='store_true',
            help='实际写入修复；默认仅输出差异，不修改数据',
        )
        mode.add_argument(
            '--dry-run',
            action='store_true',
            help='显式执行只读审计，不修改数据（默认行为）',
        )
        parser.add_argument(
            '--conversation-id',
            type=int,
            help='只检查指定会话；默认检查全部会话',
        )

    @staticmethod
    def _has_difference(profile, snapshot) -> bool:
        return any((
            profile.trust_score != snapshot.trust_score,
            profile.intent_score != snapshot.intent_score,
            (profile.emotion_trace or []) != snapshot.emotion_trace,
        ))

    def _audit_profile(self, profile, *, apply):
        if not apply:
            snapshot = replay_profile_scores(profile.conversation_id)
            return snapshot, self._has_difference(profile, snapshot)

        with transaction.atomic():
            Conversation.objects.select_for_update().get(pk=profile.conversation_id)
            locked = CustomerProfile.objects.select_for_update().get(pk=profile.pk)
            snapshot = replay_profile_scores(locked.conversation_id)
            has_difference = self._has_difference(locked, snapshot)
            if has_difference:
                locked.trust_score = snapshot.trust_score
                locked.intent_score = snapshot.intent_score
                locked.emotion_trace = snapshot.emotion_trace
                locked.save(update_fields=[
                    'trust_score', 'intent_score', 'emotion_trace', 'updated_at',
                ])
            return snapshot, has_difference

    def handle(self, *args, **options):
        profiles = CustomerProfile.objects.order_by('conversation_id')
        if options['conversation_id']:
            profiles = profiles.filter(conversation_id=options['conversation_id'])

        checked = 0
        differences = 0
        updated = 0
        for profile in profiles.iterator():
            checked += 1
            before = (
                profile.trust_score,
                profile.intent_score,
                len(profile.emotion_trace or []),
            )
            snapshot, has_difference = self._audit_profile(profile, apply=options['apply'])
            if not has_difference:
                continue
            differences += 1
            if options['apply']:
                updated += 1
            self.stdout.write(
                f'会话#{profile.conversation_id}：'
                f'信任/意向/轨迹 {before[0]}/{before[1]}/{before[2]} -> '
                f'{snapshot.trust_score}/{snapshot.intent_score}/{len(snapshot.emotion_trace)}；'
                f'已完成轮次={snapshot.completed_turns}'
            )

        mode = '已应用' if options['apply'] else '仅审计'
        message = f'{mode}：检查={checked}，差异={differences}，更新={updated}。'
        self.stdout.write(self.style.SUCCESS(message))
