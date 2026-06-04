"""CLI entry point."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from ronny.pass_analysis_lm.config import (
    ResolvedTarget,
    config_path,
    fetch_models,
    load_config,
    resolve_target,
    write_example_config,
)
from ronny.pass_analysis_lm.secrets import delete_api_key, set_api_key
from ronny.pass_analysis_lm.store import (
    PassEntry,
    get_store_dir,
    list_entry_names,
    show_entry,
)

console = Console()

_RISK_WARNING = """\
[bold red]SECURITY RISK WARNING[/bold red]

This tool decrypts your entire pass store and sends all plaintexts to an LLM.
Even when that LLM runs on a local network you accept the following risks:

  • All secrets are decrypted into process memory; they may appear in swap or core dumps.
  • The LLM server receives every secret in plaintext over the network.
  • Many LLM servers log prompts to disk or memory by default — verify yours does not.
  • Any misconfiguration in the LLM server could expose your secrets.
  • Fake tool-call injection only reduces prompt-injection risk; it does not eliminate it.

Only proceed if you:
  1. Own and fully trust the machine(s) running the LLM.
  2. Have verified the LLM server does NOT persist or log prompts.
  3. Accept that this tool is experimental and provided WITHOUT WARRANTY.
"""


@click.group()
def main() -> None:
    """Analyse a pass password store with a self-hosted LLM."""


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@main.command("run")
@click.option(
    "--store",
    "store_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to pass store (default: $PASSWORD_STORE_DIR or ~/.password-store).",
)
@click.option(
    "--provider",
    default=None,
    metavar="NAME[/MODEL]",
    help=(
        "Provider name from config, optionally followed by '/model'. "
        "Example: vllm-local  or  vllm-local/qwen/Qwen2.5-7B-Instruct"
    ),
)
@click.option("--model", default=None, help="Override the model name.")
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip the risk confirmation prompt.",
)
def run_cmd(store_dir: Path | None, provider: str | None, model: str | None, yes: bool) -> None:
    """Decrypt the pass store and analyse every entry with the configured LLM."""
    console.print(Panel(_RISK_WARNING, border_style="red"))

    if not yes:
        click.confirm("I understand the risks and want to continue", abort=True)

    config = load_config()
    try:
        target = resolve_target(provider, config, model)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(
        f"\n[bold]Provider:[/bold] {target.provider_name}  "
        f"[bold]Model:[/bold] {target.model}  "
        f"[bold]Endpoint:[/bold] {target.provider.base_url}"
    )

    resolved_store = store_dir or get_store_dir()
    asyncio.run(_run(resolved_store, target))


_DECRYPT_CONCURRENCY = 8
_BATCH_SIZE = 10


async def _decrypt(
    name: str,
    sem: asyncio.Semaphore,
    progress: Progress,
    task: object,
) -> PassEntry:
    async with sem:
        entry = PassEntry(name=name, plaintext=await show_entry(name))
        progress.advance(task)
        return entry


async def _run(store_dir: Path, target: ResolvedTarget) -> None:
    from ronny.pass_analysis_lm.analysis import (  # noqa: PLC0415 E402
        analyse_batch,
        make_agent,
    )

    agent = make_agent(target)
    console.print(f"[bold]Store:[/bold] {store_dir}")

    names = list_entry_names(store_dir)
    console.print(f"Found [bold]{len(names)}[/bold] entries.\n")

    sem = asyncio.Semaphore(_DECRYPT_CONCURRENCY)
    with Progress(console=console) as progress:
        task = progress.add_task("Decrypting entries…", total=len(names))
        entries: list[PassEntry] = list(
            await asyncio.gather(*[_decrypt(n, sem, progress, task) for n in names])
        )

    with Progress(console=console) as progress:
        task = progress.add_task("Analysing entries…", total=len(entries))
        for i in range(0, len(entries), _BATCH_SIZE):
            batch = entries[i : i + _BATCH_SIZE]
            pairs = [(e.name, e.plaintext.get_secret_value()) for e in batch]
            for ef in await analyse_batch(pairs, agent):
                console.print(Panel(ef.findings, title=f"[cyan]{ef.entry_name}[/cyan]"))
            progress.advance(task, len(batch))


# ---------------------------------------------------------------------------
# config subcommand group
# ---------------------------------------------------------------------------

@main.group("config")
def config_group() -> None:
    """Manage the configuration file."""


@config_group.command("show-path")
def config_show_path() -> None:
    """Print the path to the config file."""
    console.print(str(config_path()))


@config_group.command("init")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing config.")
def config_init(force: bool) -> None:
    """Write a starter config file (does not overwrite unless --force)."""
    path = config_path()
    if path.exists() and not force:
        console.print(f"[yellow]Config already exists:[/yellow] {path}")
        console.print("Use --force to overwrite.")
        return
    written = write_example_config()
    console.print(f"[green]Config written to:[/green] {written}")


@config_group.command("list-providers")
def config_list_providers() -> None:
    """List configured providers."""
    config = load_config()
    if not config.providers:
        console.print("[yellow]No providers configured.[/yellow] Run `config init` first.")
        return
    table = Table("Name", "Base URL", "Default model", "Pinned models")
    for name, prov in config.providers.items():
        marker = " [green](default)[/green]" if name == config.default_provider else ""
        table.add_row(
            name + marker,
            prov.base_url,
            prov.default_model,
            ", ".join(prov.models) or "—",
        )
    console.print(table)


@config_group.command("list-models")
@click.argument("provider_name")
def config_list_models(provider_name: str) -> None:
    """Fetch and list available models from PROVIDER_NAME."""
    config = load_config()
    if provider_name not in config.providers:
        available = ", ".join(config.providers) or "(none)"
        raise click.ClickException(
            f"Provider {provider_name!r} not found. Available: {available}"
        )
    try:
        target = resolve_target(provider_name, config)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    async def _fetch() -> list[str]:
        return await fetch_models(target)

    try:
        models = asyncio.run(_fetch())
    except Exception as exc:
        raise click.ClickException(f"Failed to fetch models: {exc}") from exc

    console.print(f"[bold]Models available from {provider_name}:[/bold]")
    for m in models:
        console.print(f"  {provider_name}/{m}")


@config_group.command("set-key")
@click.argument("provider_name")
@click.option("--key", "api_key", default=None, help="API key value (prompted if omitted).")
def config_set_key(provider_name: str, api_key: str | None) -> None:
    """Store an API key for PROVIDER_NAME in the system keyring."""
    config = load_config()
    if provider_name not in config.providers:
        available = ", ".join(config.providers) or "(none)"
        raise click.ClickException(
            f"Provider {provider_name!r} not found in config. Available: {available}"
        )
    if api_key is None:
        api_key = click.prompt(f"API key for {provider_name}", hide_input=True)
    set_api_key(provider_name, api_key)
    console.print(f"[green]Key stored in keyring for provider:[/green] {provider_name}")


@config_group.command("delete-key")
@click.argument("provider_name")
def config_delete_key(provider_name: str) -> None:
    """Remove the keyring-stored API key for PROVIDER_NAME."""
    try:
        delete_api_key(provider_name)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Key removed from keyring for provider:[/green] {provider_name}")


# ---------------------------------------------------------------------------
# tui
# ---------------------------------------------------------------------------

@main.command("tui")
@click.option(
    "--store",
    "store_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to pass store.",
)
@click.option(
    "--provider",
    default=None,
    metavar="NAME[/MODEL]",
    help="Provider name from config.",
)
@click.option("--model", default=None, help="Override the model name.")
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip the risk confirmation prompt.",
)
def tui_cmd(store_dir: Path | None, provider: str | None, model: str | None, yes: bool) -> None:
    """Launch the interactive TUI for pass store analysis."""
    try:
        from ronny.pass_analysis_lm.tui import PassAnalysisApp
    except ImportError:
        raise click.ClickException(
            "textual not installed. Install with: uv sync --extra tui"
        )

    app = PassAnalysisApp(
        store_dir=store_dir,
        provider=provider,
        model=model,
        yes=yes,
    )
    app.run()
