"""Deterministic audit helpers for repairing retry-inflated profile scores."""

from __future__ import annotations

from dataclasses import dataclass

from . import psychology
from .models import Message


INITIAL_PROFILE_SCORE = 20
MAX_EMOTION_TRACE = 30


@dataclass(frozen=True)
class ProfileScoreSnapshot:
    trust_score: int
    intent_score: int
    emotion_trace: list[dict]
    completed_turns: int


def replay_profile_scores(conversation_id: int) -> ProfileScoreSnapshot:
    """Replay only completed, uniquely identified user turns for one conversation."""
    completed_client_ids = set(
        Message.objects.filter(
            conversation_id=conversation_id,
            role=Message.Role.ASSISTANT,
        )
        .exclude(client_id='')
        .values_list('client_id', flat=True)
    )
    messages = Message.objects.filter(
        conversation_id=conversation_id,
        role=Message.Role.USER,
        client_id__in=completed_client_ids,
    ).order_by('created_at', 'id')

    trust_score = INITIAL_PROFILE_SCORE
    intent_score = INITIAL_PROFILE_SCORE
    emotion = 'neutral'
    emotion_trace: list[dict] = []
    completed_turns = 0
    for message in messages.iterator():
        analysis = psychology.analyze(message.content, emotion)
        emotion = analysis.get('emotion') or emotion
        trust_score = min(100, max(0, trust_score + analysis.get('trust_delta', 0)))
        intent_score = min(100, max(0, intent_score + analysis.get('intent_delta', 0)))
        emotion_trace.append({
            'emotion': emotion,
            'intent': analysis.get('intent', 'chat'),
        })
        emotion_trace = emotion_trace[-MAX_EMOTION_TRACE:]
        completed_turns += 1

    return ProfileScoreSnapshot(
        trust_score=trust_score,
        intent_score=intent_score,
        emotion_trace=emotion_trace,
        completed_turns=completed_turns,
    )
