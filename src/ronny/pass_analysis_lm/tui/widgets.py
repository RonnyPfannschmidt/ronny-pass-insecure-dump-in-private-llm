"""TUI widgets for the pass analysis interface."""

from __future__ import annotations

import re
from pathlib import Path

from rich.text import Text
from textual.widgets import RichLog, Tree
from textual.widgets._tree import TreeNode


def _mask(value: str) -> str:
    return "•" * max(len(value), 1)


def _parse_entry_content(content: str) -> list[tuple[str, str]]:
    """Parse entry content into (label, value) pairs.

    First line is the password. Subsequent lines are key: value pairs.
    Blank lines are preserved as-is. Whitespace is not stripped from values.
    """
    lines = content.splitlines()
    if not lines:
        return []

    result: list[tuple[str, str]] = [("password", lines[0])]
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


class EntryTree(Tree[str]):
    """Tree view of pass store entries — only leaf nodes are selectable."""

    ALLOW_SELECT = True

    DEFAULT_CSS_PATH = Path(__file__).parent / "styles.tcss"

    def __init__(self, store_dir: Path) -> None:
        super().__init__("Password Store", id="entries")
        self.store_dir = store_dir

    def on_mount(self) -> None:
        self._populate()

    def _populate(self) -> None:
        root = self.root
        for gpg_path in self.store_dir.rglob("*.gpg"):
            entry_name = str(gpg_path.relative_to(self.store_dir).with_suffix(""))
            parts = entry_name.split("/")
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
            node.add(parts[-1])

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


class EntryContentViewer(RichLog):
    """Shows the content of the selected entry, masked by default."""

    DEFAULT_CSS_PATH = Path(__file__).parent / "styles.tcss"

    def __init__(self, tree: EntryTree | None = None) -> None:
        super().__init__()
        self._tree = tree
        self._content_cache: dict[str, str] = {}
        self._revealed: dict[str, bool] = {}

    def _get_current_name(self) -> str | None:
        if self._tree is None:
            return None
        node = self._tree.cursor_node
        if node is None or node.children:
            return None
        return self._tree._node_path(node)

    def show_entry(self, name: str, content: str) -> None:
        self._content_cache[name] = content
        revealed = self._revealed.get(name, False)
        self._masked_render(name, content, revealed)

    def toggle_reveal(self) -> None:
        name = self._get_current_name()
        if name is None:
            return
        self._revealed[name] = not self._revealed.get(name, False)
        content = self._content_cache.get(name, "")
        self._masked_render(name, content, self._revealed[name])

    def _masked_render(self, name: str, content: str, revealed: bool) -> None:
        self.clear()
        pairs = _parse_entry_content(content)
        if not pairs:
            self.write(Text("(empty entry)", style="gray"))
            return

        self.write(Text(f"=== {name} ===", style="bold cyan"))
        for label, value in pairs:
            if label == "" and value == "":
                self.write("")
                continue
            display = value if revealed else _mask(value)
            self.write(Text(f"{label}: {display}"))
        if not revealed:
            self.write(Text("[R]eveal", style="dim italic"))


class ResultsPanel(RichLog):
    """Displays LLM analysis results."""

    DEFAULT_CSS_PATH = Path(__file__).parent / "styles.tcss"

    def clear_results(self) -> None:
        self.clear()

    def add_finding(self, entry_name: str, findings: str) -> None:
        self.write(Text(f"=== {entry_name} ===", style="bold cyan"))
        for line in findings.split("\n"):
            self.write(Text(line))
        self.write("")
