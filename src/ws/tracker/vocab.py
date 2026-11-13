"""Neutral words for cards, shared by the drafts, the config and the skills."""

import re

CARD_TYPES = ("task", "bug", "hotfix", "improvement", "feature")
UPPER_TYPES = ("epic", "initiative")
ALL_TYPES = CARD_TYPES + UPPER_TYPES
LINK_KINDS = ("blocks", "blocked_by", "relates")
REF = re.compile(r"[A-Z][A-Z0-9_]*-[1-9]\d*")
LINK_NAMES = ("blocks", "relates")
"""The link kinds the config maps to a tracker link type; `blocked_by` is `blocks` reversed."""

TYPE_LABELS = {
    "task": "Tarefa",
    "bug": "Bug",
    "hotfix": "HotFix",
    "improvement": "Melhoria",
    "feature": "Nova função",
    "epic": "Épico",
    "initiative": "Iniciativa",
}
LINK_LABELS = {
    "blocks": "bloqueia",
    "blocked_by": "é bloqueado por",
    "relates": "relaciona-se com",
}

_BASE = ("Contexto", "Pronto quando")
_BUG = (*_BASE, "Como reproduzir", "Evidência")
_SECTIONS = {
    "task": _BASE,
    "improvement": _BASE,
    "feature": _BASE,
    "bug": _BUG,
    "hotfix": (*_BUG, "Por que não espera a release"),
    "epic": ("Contexto",),
    "initiative": ("Contexto",),
}


def required_sections(type_: str) -> tuple[str, ...]:
    return _SECTIONS[type_]


STATUS_LABELS = {
    "todo": "a fazer",
    "in_progress": "em andamento",
    "review": "em code review",
    "validation": "em validação",
    "ready_deploy": "pronto para deploy",
    "blocked": "bloqueado",
    "done": "concluída",
    "cancelled": "cancelada",
}
