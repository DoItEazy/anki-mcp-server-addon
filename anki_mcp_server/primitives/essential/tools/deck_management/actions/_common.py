"""Shared deck lookup and name handling for the deck_* tools."""
from typing import Any

from ......handler_wrappers import HandlerError

# Anki's Default deck. rslib refuses to really remove it: col.decks.remove([1])
# reports success and leaves the deck in place.
DEFAULT_DECK_ID = 1


def resolve_deck(col: Any, deck_name: str) -> dict[str, Any]:
    """Return the deck dict for ``deck_name`` or raise ``not_found``.

    ``id_for_name`` matches case-insensitively and tolerates spaces around
    ``::`` -- the same lookup ``create_deck`` and ``col.decks.id`` use.
    """
    if not deck_name or not deck_name.strip():
        raise HandlerError(
            "deck_name is required and cannot be empty",
            hint="Pass the full deck name as list_decks shows it, e.g. 'Spanish::Verbs'",
            code="validation_error",
        )

    deck_id = col.decks.id_for_name(deck_name)
    # default=False: the default (True) silently falls back to the Default deck.
    deck = col.decks.get(deck_id, default=False) if deck_id is not None else None
    if not deck:
        raise HandlerError(
            f'Deck "{deck_name}" not found',
            hint="Deck names are matched case-insensitively. Use list_decks to see the exact names.",
            code="not_found",
            deck_name=deck_name,
        )
    return deck


def normalize_deck_name(name: str) -> str:
    """Trim every ``::`` component and reject empty ones.

    Mirrors rslib's own normalization, so the name we check for conflicts is
    the name Anki will actually store.
    """
    parts = [part.strip() for part in (name or "").split("::")]
    if any(part == "" for part in parts):
        raise HandlerError(
            "Deck name parts cannot be empty",
            hint="Use a name like 'Parent::Child' -- no leading, trailing or doubled '::'",
            code="validation_error",
            new_name=name,
        )
    return "::".join(parts)


def is_descendant(name: str, ancestor: str) -> bool:
    """True when ``name`` lies strictly below ``ancestor`` (case-insensitive)."""
    return name.lower().startswith(ancestor.lower() + "::")


def subdeck_ids(col: Any, deck_id: int) -> list[int]:
    """IDs of every deck below ``deck_id`` (the deck itself excluded)."""
    return [did for did in col.decks.deck_and_child_ids(deck_id) if did != deck_id]
