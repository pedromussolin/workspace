"""Neutral words for cards, shared by the drafts, the config and the skills."""

import re
import unicodedata

CARD_TYPES = ("task", "bug", "hotfix", "improvement", "feature")
UPPER_TYPES = ("epic", "initiative")
ALL_TYPES = CARD_TYPES + UPPER_TYPES
LINK_KINDS = ("blocks", "blocked_by", "relates")
"""The link kinds of a task item."""
DRAFT_LINK_KINDS = (*LINK_KINDS, "causes", "caused_by")
"""The link kinds of a `link` draft: those of an item, and the cause of an incident."""
LABEL_KEYS = ("labels", "add_labels", "remove_labels")
REF = re.compile(r"[A-Z][A-Z0-9_]*-[1-9]\d*")
LINK_NAMES = ("blocks", "relates", "causes")
"""The link kinds the config maps to a tracker link type; `blocked_by` is `blocks` reversed and
`caused_by` is `causes` reversed."""

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
    "causes": "causa",
    "caused_by": "é causado por",
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


def fold(text: str) -> str:
    """`text` for comparing names: no accents, case folded, spaces collapsed."""
    decomposed = unicodedata.normalize("NFD", text)
    bare = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(bare.casefold().split())


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
