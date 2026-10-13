"""Rename a deck."""
from typing import Annotated, Any

from pydantic import Field

from .....tool_decorator import Tool

from .actions.rename import rename_impl


@Tool(
    "deck_rename",
    "Rename a deck, or move it in the deck tree by giving it a new '::' path "
    "(e.g. 'Spanish' -> 'Languages::Spanish'). Subdecks move along and keep "
    "their relative names; missing parent decks are created. Cards, notes and "
    "review history are not touched -- only deck names change. "
    "Refuses a name that another deck already has (compared case-insensitively; "
    "Anki itself would silently add a '+' suffix instead) and refuses moving a "
    "deck into its own subdeck. A case-only change ('spanish' -> 'Spanish') is "
    "allowed; renaming to the current name changes nothing. "
    "Searches that mention the old name (filtered deck search terms, saved "
    "searches) are NOT updated. Undoable in Anki (gui_undo). "
    "Returns deck_id, old_name, new_name, renamed, subdecks_renamed and "
    "parent_decks_created.",
    title="Rename Deck",
    write=True,
    idempotent_hint=True,
    opt_in=True,
)
def deck_rename(
    deck_name: Annotated[
        str, Field(description="Current full deck name, e.g. 'Spanish::Verbs' (case-insensitive)")
    ],
    new_name: Annotated[
        str, Field(description="New full deck name; use '::' to nest, e.g. 'Languages::Spanish::Verbs'")
    ],
) -> dict[str, Any]:
    return rename_impl(deck_name=deck_name, new_name=new_name)
