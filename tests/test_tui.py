"""Tests for the TUI widget behavior using an InMemoryStore."""

from __future__ import annotations

from textual.widgets._tree import TreeNode

from ronny.pass_analysis_lm.store import InMemoryStore
from ronny.pass_analysis_lm.tui.app import PassAnalysisApp
from ronny.pass_analysis_lm.tui.widgets import EntryTree, EntryViewPanel

FAKE_ENTRIES = {
    "service/a": "secret-a\nuser: alice",
    "service/b": "secret-b\nuser: bob",
    "service/c": "secret-c\nuser: carol",
}


def _find_leaf(tree: EntryTree, name: str) -> TreeNode[str] | None:
    """Find the leaf node whose full path equals *name*."""

    def _search(node: TreeNode[str]) -> TreeNode[str] | None:
        if tree._node_path(node) == name and not node.children:
            return node
        for child in node.children:
            result = _search(child)
            if result is not None:
                return result
        return None

    return _search(tree.root)


async def _load(viewer: EntryViewPanel, pilot, tree: EntryTree, name: str) -> None:
    """Position the tree cursor, then load an entry directly into the viewer."""
    leaf = _find_leaf(tree, name)
    if leaf is not None:
        tree.move_cursor(leaf)
    viewer.show_entry(name, FAKE_ENTRIES[name])
    await pilot.pause()


async def test_cursor_navigation_updates_view() -> None:
    """Cursor movement should update the view to the entry under the cursor."""
    store = InMemoryStore(FAKE_ENTRIES)
    app = PassAnalysisApp(store=store, yes=True)

    async with app.run_test() as pilot:
        viewer = app.query_one(EntryViewPanel)
        tree = app._tree

        await _load(viewer, pilot, tree, "service/a")
        assert viewer.border_title == "service/a"

        # press down to move tree cursor to service/b
        await pilot.press("down")
        await _load(viewer, pilot, tree, "service/b")
        assert viewer.border_title == "service/b"

        # press down again to move tree cursor to service/c
        await pilot.press("down")
        await _load(viewer, pilot, tree, "service/c")
        assert viewer.border_title == "service/c"


async def test_reveal_and_switch_auto_hides() -> None:
    """Reveal entry A, switch to B — B should be masked."""
    store = InMemoryStore(FAKE_ENTRIES)
    app = PassAnalysisApp(store=store, yes=True)

    async with app.run_test() as pilot:
        viewer = app.query_one(EntryViewPanel)
        tree = app._tree

        await _load(viewer, pilot, tree, "service/a")

        # reveal entry a
        viewer.toggle_reveal()
        await pilot.pause()
        assert viewer._revealed == "service/a"

        # switch to b — should be masked (show_entry resets revealed)
        await pilot.press("down")
        await _load(viewer, pilot, tree, "service/b")
        assert viewer.border_title == "service/b"
        assert viewer._revealed is None

        # reveal b
        viewer.toggle_reveal()
        await pilot.pause()
        assert viewer._revealed == "service/b"

        # switch back to a — should be masked again
        await pilot.press("up")
        await _load(viewer, pilot, tree, "service/a")
        assert viewer.border_title == "service/a"
        assert viewer._revealed is None


async def test_table_rows_are_masked_by_default() -> None:
    """New entries should render with masked values."""
    store = InMemoryStore(FAKE_ENTRIES)
    app = PassAnalysisApp(store=store, yes=True)

    async with app.run_test() as pilot:
        viewer = app.query_one(EntryViewPanel)
        tree = app._tree

        await _load(viewer, pilot, tree, "service/a")

        row_0 = viewer.get_row_at(0)
        assert row_0[0] == "password"
        assert row_0[1] == "\u2022" * 8
        assert row_0[1] != "secret-a"

        row_1 = viewer.get_row_at(1)
        assert row_1[0] == "user"

        cell_1_1 = row_1[1]
        assert cell_1_1 == "\u2022" * 5
        assert cell_1_1 != "alice"
