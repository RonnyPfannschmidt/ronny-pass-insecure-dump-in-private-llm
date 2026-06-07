"""TUI widgets for the pass analysis interface."""

from __future__ import annotations

import re

from pydantic import SecretStr
from rich.text import Text
from textual.widgets import DataTable, RichLog, Tree
from textual.widgets._tree import TreeNode

from ronny.pass_analysis_lm.store import Store

MASK = "•••"
LOCK_ICON = ":lock:"


def _parse_entry_content(content: SecretStr) -> list[tuple[str, str]]:
    """Parse entry content into (label, value) pairs.

    First line is the password. Subsequent lines are key: value pairs.
    Blank lines are preserved as-is. Whitespace is not stripped from values.
    """
    content_str = content.get_secret_value()
    lines = content_str.splitlines()
    if not lines:
        return []

    result: list[tuple[str, str]] = [(LOCK_ICON, lines[0])]
    for line in lines[1:]:
        if not line:
            result.append(("", ""))
            continue
        match = re.match(r"^([^:]+):\s?(.*)$", line)
        if match:
            result.append((match.group(1).strip(), match.group(2)))
        else:
            result.append((line, ""))
    return result


class EntryViewPanel(DataTable[str]):
    """DataTable subclass that renders secret fields with a border title."""

    CSS_PATH = "styles.tcss"

    def __init__(self, tree: EntryTree | None = None) -> None:
        super().__init__(id="entry-table")
        self.show_header = False
        self._tree = tree
        self._content_cache: dict[str, SecretStr] = {}
        self._current_name: str | None = None
        self._revealed: str | None = None

    @property
    def is_revealed(self) -> bool:
        return self._revealed is not None

    def _get_current_name(self) -> str | None:
        if self._tree is None:
            return None
        node = self._tree.cursor_node
        if node is None or node.children:
            return None
        return self._tree._node_path(node)

    def show_entry(self, name: str, content: SecretStr) -> None:
        self._current_name = name
        self._content_cache[name] = content
        self._revealed = None
        self._render_table(name, content, False)

    def toggle_reveal(self) -> None:
        name = self._current_name
        if name is None:
            return
        self._revealed = name if self._revealed != name else None
        content = self._content_cache.get(name, SecretStr(""))
        self._render_table(name, content, self._revealed == name)

    def _render_table(self, name: str, content: SecretStr, revealed: bool) -> None:
        self.border_title = name
        super().clear(columns=True)
        self.add_columns("Field", "Value")
        pairs = _parse_entry_content(content)
        if not pairs:
            self.add_row("", "(empty entry)")
            return
        for label, value in pairs:
            if label == "" and value == "":
                self.add_row("", "")
                continue
            display = value if revealed else MASK
            self.add_row(label, display)

    def write(self, text: Text) -> None:
        """Compat shim — used by app.py for loading/error messages."""
        self.border_title = ""
        super().clear(columns=True)
        self.add_columns("")
        self.add_row(str(text))

    def clear(self) -> None:  # type: ignore[override]
        """Clear the display."""
        super().clear(columns=True)
        self.border_title = ""

    def _masked_render(self, name: str, content: SecretStr, revealed: bool) -> None:
        """Compat shim — used by app.py for cached re-render."""
        self._current_name = name
        self._render_table(name, content, revealed)


class EntryTree(Tree[str]):
    """Tree view of pass store entries — only leaf nodes are selectable."""

    ALLOW_SELECT = True

    CSS_PATH = "styles.tcss"

    def __init__(self, store: Store) -> None:
        super().__init__("", id="entries")
        self.show_root = False
        self._store = store

    def on_mount(self) -> None:
        self._populate()
        self.root.expand()

    def _populate(self) -> None:
        root = self.root
        for name in self._store.list_entry_names():
            parts = name.split("/")
            node = root
            for part in parts[:-1]:
                found = None
                for child in node.children:
                    if str(child.label) == part:
                        found = child
                        break
                if found is None:
                    found = node.add(part)
                node = found
            node.add(parts[-1], allow_expand=False)

    def _node_path(self, node: TreeNode[str]) -> str:
        """Build full entry name from node hierarchy."""
        parts: list[str] = []
        current: TreeNode[str] | None = node
        while current is not None and current.parent is not None:
            parts.append(str(current.label))
            current = current.parent
        parts.reverse()
        return "/".join(parts)

    def get_selected_names(self) -> list[str]:
        """Return names of selected leaf nodes."""
        node = self.cursor_node
        if node is None or node.children:
            return []
        return [self._node_path(node)]

    def _find_first_leaf(self, node: TreeNode[str]) -> TreeNode[str] | None:
        """Find the first leaf node in the subtree rooted at node."""
        if not node.children:
            return node
        for child in node.children:
            leaf = self._find_first_leaf(child)
            if leaf is not None:
                return leaf
        return None


class ResultsPanel(RichLog):
    """Displays LLM analysis results."""

    CSS_PATH = "styles.tcss"

    def clear_results(self) -> None:
        self.clear()

    def add_finding(self, entry_name: str, findings: str) -> None:
        self.write(Text(f"=== {entry_name} ===", style="bold cyan"))
        for line in findings.split("\n"):
            self.write(Text(line))
        self.write("")
