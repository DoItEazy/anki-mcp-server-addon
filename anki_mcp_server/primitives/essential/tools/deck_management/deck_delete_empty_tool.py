"""Delete an empty deck."""
from typing import Annotated, Any

from pydantic import Field

from .....tool_decorator import Tool

from .actions.delete_empty import delete_empty_impl


@Tool(
    "deck_delete_empty",
    "Delete a deck that contains no cards, together with its subdecks, which "
    "must be empty too. In Anki, deleting a normal deck ALWAYS deletes its "
    "cards; this tool exists so that cleaning up decks can never cost cards or "
    "review history. It refuses if any card belongs to the deck tree -- "
    "including cards that currently sit in a filtered deck but have a deck in "
    "this tree as their home deck, since Anki would delete those as well. To get "
    "rid of cards, move them with card_change_deck, or delete them with "
    "delete_notes after the user confirmed it. Also refuses the Default deck "
    "(Anki keeps it), filtered decks (use filtered_deck_delete) and deck trees "
    "containing a filtered deck. Use dry_run=true to list what would be deleted. "
    "Undoable in Anki (gui_undo). Returns deleted_decks and cards_deleted (0).",
    title="Delete Empty Deck",
    write=True,
    idempotent_hint=True,
    opt_in=True,
)
def deck_delete_empty(
    deck_name: Annotated[
        str, Field(description="Full deck name, e.g. 'Spanish::Old' (case-insensitive)")
    ],
    dry_run: Annotated[
        bool, Field(description="Only report which decks would be deleted; change nothing")
    ] = False,
) -> dict[str, Any]:
    return delete_empty_impl(deck_name=deck_name, dry_run=dry_run)
