"""E2E tests for the deck tools: deck_rename and deck_delete_empty.

IMPORTANT -- OPT-IN TOOLS, HIDDEN BY DEFAULT
---------------------------------------------
Both tools are declared ``@Tool(..., opt_in=True)``: changing the deck tree is
something the operator has to switch on explicitly. The DEFAULT e2e container
(port 3141, ``.docker/config.json``) does not opt them in -- see
test_destructive_tools_e2e.py's ``TestOptInToolsHiddenByDefault`` for that HIDE
half. This file runs against the FILTERED container (port 3142,
``.docker/config-filtered.json``, which lists both in ``enabled_opt_in_tools``)
via the ``e2e-filtered-test`` Makefile target -- see CLAUDE.md's
"Two test suites".

What these tests pin down are the two Anki behaviours the tools exist to
guard against: a rename onto an existing name is silently suffixed with '+'
by Anki, and deleting a normal deck deletes its cards -- including cards a
filtered deck has borrowed from it.
"""
from __future__ import annotations

import pytest

from .conftest import unique_id
from .helpers import SERVER_URL, call_tool, delete_filtered_deck, list_tools


@pytest.fixture(autouse=True)
def _require_filtered_server():
    """Skip this whole file unless pointed at the filtered server (port 3142).

    Keyed on the SERVER URL, not on tool absence, so that a reveal regression
    on the filtered server fails loudly instead of quietly skipping.
    """
    if ":3142" not in SERVER_URL:
        pytest.skip(
            "deck_rename/deck_delete_empty are opt-in tools only exposed by the "
            "filtered server (port 3142, .docker/config-filtered.json); "
            f"MCP_SERVER_URL is currently {SERVER_URL!r}. Run via "
            "'make e2e-filtered-test'."
        )


def _deck_names() -> set[str]:
    return {d["name"] for d in call_tool("list_decks")["decks"]}


def _create_deck(deck_name: str) -> int:
    """create_deck caps nesting at 2 levels -- fail loudly on a setup error
    instead of letting it surface as a confusing failure further down."""
    result = call_tool("create_deck", {"deck_name": deck_name})
    assert result.get("isError") is not True, f"setup: create_deck failed: {result}"
    return result["deckId"]


def _add_note(deck_name: str, uid: str) -> int:
    _create_deck(deck_name)
    result = call_tool("add_note", {
        "deck_name": deck_name,
        "model_name": "Basic",
        "fields": {"Front": f"DeckMgmt Front {uid}", "Back": f"DeckMgmt Back {uid}"},
    })
    assert "note_id" in result, f"Failed to create test note: {result}"
    return result["note_id"]


class TestDeckToolsRevealed:
    def test_both_tools_listed(self):
        names = {t["name"] for t in list_tools()}
        assert {"deck_rename", "deck_delete_empty"} <= names, sorted(names)


class TestDeckRename:
    def test_rename_moves_subdecks_and_cards(self):
        uid = unique_id()
        old = f"E2E_DMOld{uid}"
        note_id = _add_note(f"{old}::Child", uid)

        new = f"E2E_DMMoved{uid}::Renamed"
        result = call_tool("deck_rename", {"deck_name": old, "new_name": new})

        assert result.get("isError") is not True, result
        assert result["renamed"] is True
        assert result["new_name"] == new
        assert result["parent_decks_created"] == [f"E2E_DMMoved{uid}"]
        assert [s["new_name"] for s in result["subdecks_renamed"]] == [f"{new}::Child"]

        names = _deck_names()
        assert new in names and f"{new}::Child" in names
        assert old not in names

        found = call_tool("find_notes", {"query": f'"deck:{new}::Child"'})
        assert note_id in found["noteIds"], "the card must move with its deck"

    def test_case_only_rename(self):
        uid = unique_id()
        old = f"E2E::dmcase{uid}"
        _create_deck(old)

        result = call_tool("deck_rename", {"deck_name": old, "new_name": f"E2E::DMCASE{uid}"})

        assert result.get("isError") is not True, result
        assert result["new_name"] == f"E2E::DMCASE{uid}"

    def test_same_name_is_a_no_op(self):
        uid = unique_id()
        name = f"E2E::DMSame{uid}"
        _create_deck(name)

        result = call_tool("deck_rename", {"deck_name": name, "new_name": name})

        assert result.get("isError") is not True, result
        assert result["renamed"] is False

    def test_existing_name_refused_without_plus_suffix(self):
        """Anki itself would rename to 'Taken+' -- the tool must refuse instead."""
        uid = unique_id()
        source = f"E2E::DMSrc{uid}"
        taken = f"E2E::DMTaken{uid}"
        _create_deck(source)
        _create_deck(taken)

        result = call_tool("deck_rename", {"deck_name": source, "new_name": taken.lower()})

        assert result.get("isError") is True
        assert "already exists" in str(result)
        names = _deck_names()
        assert source in names
        assert f"{taken}+" not in names and f"{taken.lower()}+" not in names

    def test_move_into_own_subdeck_refused(self):
        uid = unique_id()
        name = f"E2E::DMLoop{uid}"
        _create_deck(name)

        result = call_tool("deck_rename", {"deck_name": name, "new_name": f"{name}::Inner"})

        assert result.get("isError") is True
        assert name in _deck_names()

    def test_unknown_deck(self):
        result = call_tool("deck_rename", {
            "deck_name": f"E2E::DMMissing{unique_id()}", "new_name": "E2E::Whatever",
        })
        assert result.get("isError") is True
        assert "not found" in str(result).lower()

    def test_empty_name_part_refused(self):
        uid = unique_id()
        name = f"E2E::DMParts{uid}"
        _create_deck(name)

        result = call_tool("deck_rename", {"deck_name": name, "new_name": "E2E::::Broken"})

        assert result.get("isError") is True


class TestDeckDeleteEmpty:
    def test_dry_run_then_delete_empty_tree(self):
        uid = unique_id()
        root = f"E2E_DMEmpty{uid}"
        _create_deck(f"{root}::Sub")

        preview = call_tool("deck_delete_empty", {"deck_name": root, "dry_run": True})
        assert preview.get("isError") is not True, preview
        assert preview["dry_run"] is True
        assert sorted(preview["decks_to_delete"]) == [root, f"{root}::Sub"]
        assert root in _deck_names(), "dry_run must not delete anything"

        result = call_tool("deck_delete_empty", {"deck_name": root})
        assert result.get("isError") is not True, result
        assert result["cards_deleted"] == 0
        names = _deck_names()
        assert root not in names and f"{root}::Sub" not in names

        again = call_tool("deck_delete_empty", {"deck_name": root})
        assert again.get("isError") is True
        assert "not found" in str(again).lower()

    def test_deck_with_card_in_subdeck_refused(self):
        uid = unique_id()
        root = f"E2E_DMFull{uid}"
        note_id = _add_note(f"{root}::Child", uid)

        result = call_tool("deck_delete_empty", {"deck_name": root})

        assert result.get("isError") is True
        assert "not empty" in str(result)
        assert f"{root}::Child" in _deck_names()
        assert call_tool("notes_info", {"notes": [note_id]})["count"] == 1

    def test_card_borrowed_by_filtered_deck_refused(self):
        """Anki would delete a card a filtered deck has borrowed from the deck."""
        uid = unique_id()
        home = f"E2E::DMHome{uid}"
        note_id = _add_note(home, uid)
        filtered = call_tool("filtered_deck_upsert", {
            "name": f"E2E::DMCram{uid}",
            "search_terms": [{"search": f'"deck:{home}"', "limit": 100, "order": "random"}],
        })
        assert filtered["card_count"] == 1, filtered
        try:
            result = call_tool("deck_delete_empty", {"deck_name": home})

            assert result.get("isError") is True
            assert "not empty" in str(result)
            assert home in _deck_names()
            assert call_tool("notes_info", {"notes": [note_id]})["count"] == 1
        finally:
            delete_filtered_deck(filtered["deck_id"])

    def test_filtered_deck_refused(self):
        uid = unique_id()
        filtered = call_tool("filtered_deck_upsert", {
            "name": f"E2E::DMFiltered{uid}",
            "search_terms": [{"search": "deck:E2E::NoSuchDeck", "limit": 10, "order": "random"}],
        })
        try:
            result = call_tool("deck_delete_empty", {"deck_name": f"E2E::DMFiltered{uid}"})

            assert result.get("isError") is True
            assert "filtered_deck_delete" in str(result)
        finally:
            delete_filtered_deck(filtered["deck_id"])

    def test_default_deck_refused(self):
        result = call_tool("deck_delete_empty", {"deck_name": "Default"})

        assert result.get("isError") is True
        assert "Default" in str(result)
        assert "Default" in _deck_names()
