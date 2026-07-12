from __future__ import annotations

import re
from dataclasses import replace

from .models import Classification, Comment
from .topics import normalize_topic


# Written to _Processed so interrupted cleanup runs resume instead of starting over.
CLASSIFIER_VERSION = "concrete-creator-directed-v4"

_HARD_REJECTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("social/play request", re.compile(
        r"\b(play with me|play together|add me|friend me|invite me|your nickname|"
        r"join (?:the |your )?(?:next )?(?:stream|game)|can i (?:join|play)|"
        r"would love to participate|with viewers|who wants to (?:play|join)|"
        r"trying to find players|looking for players)\b", re.I)),
    ("technical support/access request", re.compile(
        r"\b(send me (?:the )?link|server link|can(?:not|'t)? (?:join|connect)|"
        r"help me (?:join|connect|download)|how (?:do|can) i (?:get|join|download|install|connect)|"
        r"how to (?:get|join|download|install|connect)|where do i find|does someone know how|"
        r"what am i missing|ps plus)\b", re.I)),
    ("server/infrastructure request", re.compile(
        r"\b(more servers in|servers? in asia|add more servers|server regions?)\b", re.I)),
    ("schedule/attendance question", re.compile(
        r"\b(when do you record|when is (?:the )?next stream|are you (?:online|live)|"
        r"plans? to join (?:the )?(?:next )?stream)\b", re.I)),
    ("naming brainstorm", re.compile(
        r"\b(brainstorm(?:ing)? names?|hybrid class|come up with (?:a )?(?:name|nickname)|"
        r"what (?:should|would|do) (?:we|you|i) call)\b", re.I)),
    ("channel appearance feedback", re.compile(
        r"\b(channel avatar|new avatar|profile picture|red version of (?:the |your )?avatar)\b", re.I)),
    ("joke or meme", re.compile(
        r"\b(alcoholism|liver failure|101 players?|pick up a dolphin)\b|"
        r"^\s*(?:gw\s*[12]|garden ops)\s+but\b|\b(?:hop on|i'll hop on)\s+taco bandits\b", re.I)),
    ("vague callback or gameplay coaching", re.compile(
        r"\b(try (?:the )?tip i sent|tip i sent|use your (?:fricking )?jackhammer|"
        r"more matches like that|this one|that one)\b", re.I)),
)

_QUESTION_WITH_VIDEO_INTENT = re.compile(
    r"\b(have you (?:played|tried|checked out|used)|"
    r"(?:can|could|would|will) you (?:play|try|test|make|show|showcase|cover|review|revisit|customize)|"
    r"are you (?:going to|gonna|planning to) (?:play|try|make|cover|stream)|"
    r"playthrough|video (?:about|on|covering)|what about .{0,30}gameplay|did i miss (?:that |the )?video)\b", re.I)

_CREATOR_ACTION = re.compile(
    r"\b(?:you|u) (?:should|need to|have to|could)\b|"
    r"\b(?:can|could|would|will) (?:you|u)\b|"
    r"\b(?:please )?(?:try|play as|make|showcase|test|revisit|review|customize|rank|cover)\b|"
    r"\b(?:video|stream|playthrough|tier list|challenge|breakdown|comparison|next)\b|"
    r"\b(?:i recommend|i suggest|would love to see|wanna see|want to see|more .{0,40} content)\b|"
    r"\b(?:aconsejo|recomiendo|sugiero|deber[ií]as|prueba|juega|советую)\b", re.I)

_SERIES_NUDGE = re.compile(r"\b(?:ice|toxic|fire|power) next+\b", re.I)

_SPECULATIVE_ONLY = re.compile(
    r"\b(idea for (?:a|an) .{0,30}(?:weapon|class|item)|should be added to (?:the )?(?:game|mod)|"
    r"imagine (?:a|an)|they should (?:add|give)|wish (?:they|we) (?:added|got|had|ported))\b", re.I)


def enforce_concrete_policy(comment: Comment, result: Classification) -> Classification:
    """Apply deterministic high-precision guardrails after model classification."""
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
                       rationale="Rejected by concrete-idea policy: viewer invention or developer-facing wish.")

    if normalized.idea_type in {"recommendation", "loadout_or_strategy", "other"}:
        if not (_CREATOR_ACTION.search(text) or _SERIES_NUDGE.search(text)):
            return replace(normalized, is_idea=False, idea_type="not_an_idea", summary="", topic="",
                           rationale="Rejected by concrete-idea policy: no creator-directed action.")

    if not normalized.summary.strip() or not normalized.topic.strip():
        return replace(normalized, is_idea=False, idea_type="not_an_idea", summary="", topic="",
                       rationale="Rejected by concrete-idea policy: missing a usable subject or topic.")
    return normalized
