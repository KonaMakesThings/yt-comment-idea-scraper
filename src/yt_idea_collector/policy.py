from __future__ import annotations

import re
from dataclasses import replace

from .models import Classification, Comment
from .topics import normalize_topic


# Written to _Processed so interrupted cleanup runs resume instead of starting over.
CLASSIFIER_VERSION = "generic-creator-directed-v5"

_HARD_REJECTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("social/play request", re.compile(
        r"\b(play with me|play together|add me|friend me|invite me|"
        r"join (?:the |your )?(?:next )?(?:stream|game)|can i (?:join|play)|"
        r"with viewers|looking for players)\b", re.I)),
    ("technical support/access request", re.compile(
        r"\b(send me (?:the )?link|can(?:not|'t)? (?:join|connect)|"
        r"help me (?:join|connect|download)|how (?:do|can) i (?:get|join|download|install|connect)|"
        r"how to (?:get|join|download|install|connect)|where do i find|what am i missing)\b", re.I)),
    ("infrastructure request", re.compile(
        r"\b(add|create|open|provide|set up) (?:more |another )?(?:servers?|regions?|channels?)\b", re.I)),
    ("schedule/attendance question", re.compile(
        r"\b(when do you record|when is (?:the )?next stream|are you (?:online|live)|"
        r"plans? to join (?:the )?(?:next )?stream)\b", re.I)),
    ("naming brainstorm", re.compile(
        r"\b(brainstorm(?:ing)? names?|come up with (?:a )?(?:name|nickname)|"
        r"what (?:should|would|do) (?:we|you|i) call)\b", re.I)),
    ("channel appearance feedback", re.compile(
        r"\b(channel avatar|profile picture|banner image|channel logo)\b", re.I)),
    ("vague callback", re.compile(
        r"\b(try (?:the )?(?:tip|thing) i sent|the (?:tip|thing) i mentioned|more like that)\b", re.I)),
)

_QUESTION_WITH_VIDEO_INTENT = re.compile(
    r"\b(have you (?:played|tried|checked out|used)|"
    r"(?:can|could|would|will) you (?:play|try|test|make|show|showcase|cover|review|revisit|customize)|"
    r"are you (?:going to|gonna|planning to) (?:play|try|make|cover|stream)|"
    r"playthrough|video (?:about|on|covering)|did i miss (?:that |the )?video)\b", re.I)

_CREATOR_ACTION = re.compile(
    r"\b(?:you|u) (?:should|need to|have to|could)\b|"
    r"\b(?:can|could|would|will) (?:you|u)\b|"
    r"\b(?:please )?(?:try|play as|make|showcase|test|revisit|review|customize|rank|cover|explain|compare)\b|"
    r"\b(?:video|stream|playthrough|tier list|challenge|breakdown|comparison|tutorial|guide)\b|"
    r"\b(?:i recommend|i suggest|would love to see|want to see|more .{0,40} content)\b", re.I)

_SPECULATIVE_ONLY = re.compile(
    r"\b(idea for (?:a|an) .{0,40}(?:feature|weapon|class|item)|"
    r"should be added to (?:the )?(?:game|app|product)|imagine (?:a|an)|"
    r"they should (?:add|give)|wish (?:they|we) (?:added|got|had|ported))\b", re.I)


def enforce_concrete_policy(comment: Comment, result: Classification) -> Classification:
    """Apply generic high-precision guardrails after model classification."""
    normalized = replace(result, topic=normalize_topic(result.topic))
    if not normalized.is_idea:
        return normalized

    text = comment.text.strip()
    for reason, pattern in _HARD_REJECTS:
        if pattern.search(text):
            return replace(normalized, is_idea=False, idea_type="not_an_idea", summary="",
                           topic="", rationale=f"Rejected by concrete-idea policy: {reason}.")

    if normalized.idea_type == "implied_concept":
        return replace(normalized, is_idea=False, idea_type="not_an_idea", summary="", topic="",
                       rationale="Rejected by concrete-idea policy: speculative concept without creator direction.")

    if normalized.idea_type == "question" and not _QUESTION_WITH_VIDEO_INTENT.search(text):
        return replace(normalized, is_idea=False, idea_type="not_an_idea", summary="", topic="",
                       rationale="Rejected by concrete-idea policy: ordinary/support question, not a video request.")

    if _SPECULATIVE_ONLY.search(text) and not _CREATOR_ACTION.search(text):
        return replace(normalized, is_idea=False, idea_type="not_an_idea", summary="", topic="",
                       rationale="Rejected by concrete-idea policy: invention or product wish without creator direction.")

    if normalized.idea_type in {"recommendation", "loadout_or_strategy", "other"}:
        if not _CREATOR_ACTION.search(text):
            return replace(normalized, is_idea=False, idea_type="not_an_idea", summary="", topic="",
                           rationale="Rejected by concrete-idea policy: no creator-directed action.")

    if not normalized.summary.strip() or not normalized.topic.strip():
        return replace(normalized, is_idea=False, idea_type="not_an_idea", summary="", topic="",
                       rationale="Rejected by concrete-idea policy: missing a usable subject or topic.")
    return normalized
