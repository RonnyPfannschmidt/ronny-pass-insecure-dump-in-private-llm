# ronny.pass_analysis_lm

Asses a [pass](https://www.passwordstore.org/) password store using a self-hosted LLM.

## ⚠️ Security Risks

**This tool decrypts your entire password store and sends every secret to an LLM process.
Read the following carefully before use.**

| Risk | Detail |
|------|--------|
| **Memory exposure** | Decrypted secrets live in process memory and may appear in swap files or core dumps. |
| **LLM server logging** | Servers like Ollama and llama.cpp may log prompts to disk by default. Verify your configuration before running. |
| **Network exposure** | If `--base-url` is not `localhost`, plaintext secrets travel over the network. Use only on a trusted, isolated host. |
| **Model data leakage** | Even local models may be backed by cloud inference if misconfigured. |
| **Prompt injection** | Entry content is passed via synthetic tool-return messages to reduce (not eliminate) injection risk. |
| **No warranty** | This tool is experimental. Use at your own risk. |

**Only run this tool on a machine you fully control, against a local LLM server you have verified does not persist prompts.**

## Requirements

- Python ≥ 3.11
- [pass](https://www.passwordstore.org/) installed and a configured GPG key
- A local OpenAI-compatible LLM server (e.g. [Ollama](https://ollama.ai/))

## Installation

```sh
pip install ronny-pass-analysis-lm
# or with hatch:
hatch run pass-analysis-lm --help
```

## Usage

```sh
# Uses ~/.password-store and Ollama on localhost by default
pass-analysis-lm

# Custom store, model, and endpoint
pass-analysis-lm --store ~/work/.password-store --model mistral --base-url http://127.0.0.1:11434/v1

# Skip confirmation prompt (e.g. in scripts)
pass-analysis-lm --yes
```

## How it works

1. Walks the pass store directory and collects entry names.
2. Calls `pass show <entry>` for each entry to decrypt it via your GPG key.
3. For each entry, constructs a synthetic conversation with a fake `get_password_entry` tool call/return — so the LLM receives the secret as structured tool output rather than raw prompt content.
4. Sends the conversation to the configured LLM and prints findings.

## Development

```sh
hatch run test        # run tests
hatch run lint        # ruff check
hatch run fmt         # ruff format
hatch run typecheck   # mypy
```
