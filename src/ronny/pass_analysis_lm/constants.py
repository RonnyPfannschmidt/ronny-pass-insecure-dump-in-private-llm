"""Shared constants."""

_RISK_WARNING = """\
[bold red]SECURITY RISK WARNING[/bold red]

This tool decrypts your entire pass store and sends all plaintexts to an LLM.
Even when that LLM runs on a local network you accept the following risks:

  \u2022 All secrets are decrypted into process memory
  \u2022 The LLM server receives every secret in plaintext over the network.
  \u2022 Server logs or misconfigurations could put unencrypted secrets on disk
  \u2022 Any misconfiguration in the LLM server could expose your secrets.
Only proceed if you:
  1. Own and fully trust the machine(s) running the LLM.
  2. Have verified the LLM server does NOT persist or log prompts.
  3. Accept that this tool is experimental and provided WITHOUT WARRANTY.
"""
