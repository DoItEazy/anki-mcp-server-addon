"""Implementation for the deck_delete_empty tool."""
from typing import Any

from ......handler_wrappers import HandlerError, get_col
from ._common import DEFAULT_DECK_ID, resolve_deck


def delete_empty_impl(deck_name: str, dry_run: bool) -> dict[str, Any]:
    """Delete a deck and its subdecks, but only if not a single card would go.

    Deleting a NORMAL deck in Anki deletes its cards (rslib's
    ``remove_single_deck`` -> ``delete_all_cards_in_normal_deck``), and that
    includes cards that currently sit in a filtered deck but have this deck as
    their home deck (``odid``). So "empty" is checked against both ``did`` and
    ``odid`` across the whole subtree, and any filtered deck inside the subtree
    is refused outright rather than reasoned about.
    """
    col = get_col()
    deck = resolve_deck(col, deck_name)
    deck_id = deck["id"]
    name = deck["name"]

    if deck_id == DEFAULT_DECK_ID:
        raise HandlerError(
            "The Default deck cannot be deleted",
            hint="Anki always keeps the Default deck. Rename it with deck_rename instead.",
            code="validation_error",
            deck_name=name,
        )
    if deck.get("dyn"):
        raise HandlerError(
            "This is a filtered deck",
            hint="Use filtered_deck_delete -- it returns the cards to their home decks first.",
            code="validation_error",
            deck_name=name,
            deck_id=deck_id,
        )

    tree_ids = list(col.decks.deck_and_child_ids(deck_id))
    filtered_inside = [
        col.decks.name_if_exists(did)
        for did in tree_ids
        if (col.decks.get(did, default=False) or {}).get("dyn")
    ]
    if filtered_inside:
        raise HandlerError(
            "The deck tree contains filtered decks",
            hint="Delete them first with filtered_deck_delete (that returns their "
                 "cards to their home decks), then retry.",
            code="validation_error",
            deck_name=name,
            filtered_decks=filtered_inside,
        )

    # Each card counted once, against its home deck: odid when it is
    # borrowed by a filtered deck, did otherwise.
    ids_sql = "(" + ",".join(str(int(did)) for did in tree_ids) + ")"
    rows = col.db.all(
        "select (case when odid != 0 then odid else did end), count() from cards "
        f"where did in {ids_sql} or odid in {ids_sql} group by 1"
    )
    if rows:
        cards_by_deck = {
            (col.decks.name_if_exists(did) or str(did)): count for did, count in rows
        }
        raise HandlerError(
            f'Deck "{name}" is not empty: {sum(cards_by_deck.values())} card(s) '
            "would be deleted with it",
            hint="This tool only deletes decks without any cards, so nothing can be "
                 "lost. Move the cards elsewhere with card_change_deck, or delete "
                 "them with delete_notes after the user confirmed it, then retry. "
                 "Cards currently borrowed by a filtered deck count too.",
            code="validation_error",
            deck_name=name,
            cards_by_deck=cards_by_deck,
        )

    deck_names = [col.decks.name_if_exists(did) for did in tree_ids]

    if dry_run:
        return {
            "dry_run": True,
            "deck_id": deck_id,
            "deck_name": name,
            "decks_to_delete": deck_names,
            "message": f"Dry run: would delete {len(deck_names)} empty deck(s). "
                       "Nothing was changed.",
        }

    try:
        changes = col.decks.remove([deck_id])
    except Exception as e:
        raise HandlerError(
            f"Anki refused to delete the deck: {e}",
            hint="Nothing was changed. Use list_decks to check the deck.",
            code="operation_failed",
            deck_name=name,
        ) from e

    result: dict[str, Any] = {
        "dry_run": False,
        "deck_id": deck_id,
        "deck_name": name,
        "deleted_decks": deck_names,
        "cards_deleted": changes.count,
        "message": f"Deleted {len(deck_names)} empty deck(s)",
        "hint": "Undo with gui_undo if this was a mistake.",
    }
    # Verified, not assumed: the emptiness check above runs on the main thread
    # right before the delete, so this should never trigger.
    if changes.count:
        result["warning"] = (
            f"Anki reported {changes.count} deleted card(s) although the deck "
            "tree was checked to be empty. Undo with gui_undo now."
        )
    return result
