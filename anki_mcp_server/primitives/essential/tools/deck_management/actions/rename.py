"""Implementation for the deck_rename tool."""
from typing import Any

from ......handler_wrappers import HandlerError, get_col
from ._common import is_descendant, normalize_deck_name, resolve_deck, subdeck_ids


def rename_impl(deck_name: str, new_name: str) -> dict[str, Any]:
    """Rename a deck (and with it, its whole subtree).

    rslib's ``rename_deck`` already moves subdecks along and creates missing
    parents. Two of its behaviours are unsafe for an AI caller, so they are
    refused up front instead:

    * a name that another deck already has is NOT an error in Anki -- it
      silently appends ``+`` ("Beta" -> "Beta+") until the name is unique;
    * moving a deck below itself is accepted and produces a scrambled tree
      (``Parent`` -> ``Parent::Child::Inner`` drags ``Parent::Child`` along to
      ``Parent::Child::Inner::Child``).
    """
    col = get_col()
    deck = resolve_deck(col, deck_name)
    deck_id = deck["id"]
    old_name = deck["name"]
    target = normalize_deck_name(new_name)

    if target == old_name:
        return {
            "deck_id": deck_id,
            "old_name": old_name,
            "new_name": old_name,
            "renamed": False,
            "subdecks_renamed": [],
            "parent_decks_created": [],
            "message": f'Deck "{old_name}" already has this name; nothing changed',
        }

    # A case-only change ("spanish" -> "Spanish") resolves to the deck itself.
    existing_id = col.decks.id_for_name(target)
    if existing_id is not None and existing_id != deck_id:
        existing_name = col.decks.name_if_exists(existing_id) or target
        raise HandlerError(
            f'A deck named "{existing_name}" already exists',
            hint="Deck names are unique (case-insensitively); Anki would silently "
                 "rename this deck to a '+'-suffixed name instead. Choose another "
                 "name, or move the cards with card_change_deck.",
            code="duplicate",
            deck_name=old_name,
            new_name=target,
            existing_deck_id=existing_id,
        )

    if is_descendant(target, old_name):
        raise HandlerError(
            "A deck cannot be moved into its own subdeck",
            hint=f'"{target}" lies inside "{old_name}". Pick a path outside it.',
            code="validation_error",
            deck_name=old_name,
            new_name=target,
        )

    subdecks_before = {
        did: col.decks.name_if_exists(did) for did in subdeck_ids(col, deck_id)
    }
    parents = target.split("::")[:-1]
    missing_parents = [
        "::".join(parents[: i + 1])
        for i in range(len(parents))
        if col.decks.id_for_name("::".join(parents[: i + 1])) is None
    ]

    try:
        col.decks.rename(deck_id, target)
    except Exception as e:
        raise HandlerError(
            f"Anki refused to rename the deck: {e}",
            hint="Nothing was changed. Use list_decks to check the current deck names.",
            code="operation_failed",
            deck_name=old_name,
            new_name=target,
        ) from e

    stored_name = col.decks.name_if_exists(deck_id) or target
    result: dict[str, Any] = {
        "deck_id": deck_id,
        "old_name": old_name,
        "new_name": stored_name,
        "renamed": True,
        "subdecks_renamed": [
            {
                "deck_id": did,
                "old_name": before,
                "new_name": col.decks.name_if_exists(did),
            }
            for did, before in subdecks_before.items()
        ],
        "parent_decks_created": missing_parents,
        "message": f'Renamed deck "{old_name}" to "{stored_name}"',
        "hint": "Cards, notes and review history are unchanged. Filtered deck "
                "searches or saved searches that mention the old name were not "
                "updated. Undo with gui_undo if this was a mistake.",
    }
    # Verified, not assumed: the pre-checks above should make this impossible.
    if stored_name.lower() != target.lower():
        result["warning"] = (
            f'Anki stored the name as "{stored_name}" instead of "{target}"'
        )
    return result
