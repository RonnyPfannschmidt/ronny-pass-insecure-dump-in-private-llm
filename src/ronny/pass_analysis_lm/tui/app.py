"""Main TUI application."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog

from ronny.pass_analysis_lm.analysis import analyse_batch, make_agent
from ronny.pass_analysis_lm.config import load_config, resolve_target
from ronny.pass_analysis_lm.constants import _RISK_WARNING
from ronny.pass_analysis_lm.store import (
    GpgStore,
    PassEntry,
    Store,
    get_store_dir,
)
from ronny.pass_analysis_lm.tui.widgets import (
    EntryTree,
    EntryViewPanel,
    ResultsPanel,
)


class RiskWarningScreen(Screen[bool]):
    """Modal dialog showing the security risk warning."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"

    def compose(self) -> ComposeResult:
        with Container(id="warning-box"):
            yield RichLog(id="warning-log")
        with Container(id="buttons"):
            yield Button("I understand, continue", id="continue", variant="primary")
            yield Button("Cancel", id="cancel", variant="warning")

    def on_mount(self) -> None:
        log = self.query_one("#warning-log", RichLog)
        log.write(Text(_RISK_WARNING, style="red"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.dismiss(True)
        else:
            self.dismiss(False)


class PassAnalysisApp(App[None]):
    """Interactive TUI for pass store analysis."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"

    BINDINGS = [
        ("a", "analyze_all", "Analyze All"),
        ("s", "analyze_selected", "Analyze Selected"),
        ("r", "toggle_reveal", "Reveal/Hide"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        store: Store | None = None,
        store_dir: Path | None = None,
        provider: str | None = None,
        model: str | None = None,
        yolo: bool = False,
    ) -> None:
        super().__init__()
        self._store = store or GpgStore(store_dir or get_store_dir())
        self.provider = provider
        self.model = model
        self._risk_acknowledged = yolo

    def compose(self) -> ComposeResult:
        yield Header()
        self._tree = EntryTree(self._store)
        with Container(id="main-grid"):
            yield self._tree
            with Container(id="right-panel"):
                yield EntryViewPanel(self._tree)
                yield ResultsPanel()
        yield Footer()

    def on_mount(self) -> None:
        self._content_viewer = self.query_one(EntryViewPanel)
        self._results = self.query_one(ResultsPanel)
        self.call_later(self._initialize_cursor)

    def _initialize_cursor(self) -> None:
        cursor = self._tree.cursor_node
        if cursor is not None and not cursor.children and self._tree._node_path(cursor):
            return
        for child in self._tree.root.children:
            leaf = self._tree._find_first_leaf(child)
            if leaf is not None:
                self._tree.move_cursor(leaf)
                break

    def on_tree_node_highlighted(self, event: EntryTree.NodeHighlighted[str]) -> None:
        node = event.node
        if node.children:
            return
        name = self._tree._node_path(node)
        self._load_entry(name)

    def _load_entry(self, name: str) -> None:
        self._content_viewer._revealed = None
        if name in self._content_viewer._content_cache:
            self._content_viewer._masked_render(
                name, self._content_viewer._content_cache[name], False
            )
        else:
            self._fetch_entry(name)

    def _fetch_entry(self, name: str) -> None:
        self._content_viewer.clear()
        self._content_viewer.write(Text("Loading...", style="dim italic"))

        async def fetch_and_show() -> None:
            try:
                content = await self._store.show_entry(name)
                if name not in self._content_viewer._content_cache:
                    self._content_viewer.show_entry(name, content)
            except Exception as exc:
                self._content_viewer.clear()
                self._content_viewer.write(Text(f"Error: {exc}", style="red"))

        self.run_worker(fetch_and_show(), thread=False)

    def action_toggle_reveal(self) -> None:
        self._content_viewer.toggle_reveal()

    async def _check_risk_warning(self) -> bool:
        if self._risk_acknowledged:
            return True
        result = await self.push_screen_wait(RiskWarningScreen())
        if result:
            self._risk_acknowledged = True
        return result

    def action_analyze_all(self) -> None:
        self._run_analysis_mode("all")

    def action_analyze_selected(self) -> None:
        names = self._tree.get_selected_names()
        if not names:
            self.notify("No entries selected", severity="warning")
            return
        self._run_analysis(names)

    def _run_analysis_mode(self, mode: str) -> None:
        async def check_and_run() -> None:
            if not await self._check_risk_warning():
                return
            names: list[str] = []
            if mode == "all":
                names = self._store.list_entry_names()
            self._run_analysis(names)

        self.run_worker(check_and_run(), thread=False)

    def _run_analysis(self, names: list[str]) -> None:
        self._results.clear_results()
        self._results.write(Text("Analysing...", style="bold yellow"))

        async def do_analysis() -> None:
            config = load_config()
            try:
                target = resolve_target(self.provider, config, self.model)
            except ValueError as exc:
                self._results.write(Text(str(exc), style="red"))
                self.notify(str(exc), severity="error")
                return

            agent = make_agent(target)
            entries: list[PassEntry] = []

            for name in names:
                try:
                    content = await self._store.show_entry(name)
                    entries.append(PassEntry(name=name, plaintext=(content)))
                except Exception as exc:
                    self._results.write(
                        Text(f"Error loading {name}: {exc}", style="red")
                    )

            if not entries:
                self._results.write(Text("No entries to analyze", style="yellow"))
                return

            batch_size = 10
            for i in range(0, len(entries), batch_size):
                batch = entries[i : i + batch_size]
                pairs = [(e.name, e.plaintext.get_secret_value()) for e in batch]
                try:
                    findings = await analyse_batch(pairs, agent)
                    for ef in findings:
                        self._results.add_finding(ef.entry_name, ef.findings)
                except Exception as exc:
                    self._results.write(Text(f"Analysis error: {exc}", style="red"))

        self.run_worker(do_analysis(), thread=False)
