"""Deck tools package - imports each deck_* tool to trigger @Tool registration."""
from .deck_rename_tool import deck_rename
from .deck_delete_empty_tool import deck_delete_empty

__all__ = [
    "deck_rename",
    "deck_delete_empty",
]
