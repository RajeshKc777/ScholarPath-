# ScholarPath AI

Local-first desktop assistant for finding **legitimate** scholarship
opportunities and understanding eligibility. Windows-first, Python + PySide6.

> **Status: Milestone 1.** The desktop shell, configuration handling, and chat
> loop work against an **offline stub gateway**. There is no network access, no
> model, and no scholarship research in this build. Nothing in the UI pretends
> otherwise.

Full product specification: [`goals.md`](goals.md) · Build log: [`achievements.md`](achievements.md)

## Requirements

- Windows 10/11 (other platforms work for development)
- Python 3.11+ (3.11 is the tested target)
- No network access required for this milestone

## Setup

```powershell
git clone <repo> scholarpath
cd scholarpath
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Run

```powershell
scholarpath              # or: python -m scholarpath
scholarpath --init-config   # write the config template and exit
scholarpath --version
```

The first run needs no configuration: defaults use the stub gateway.

## Test

```powershell
pytest
```

Tests cover configuration validation, the gateway contract, and chat turn
handling. They use a synchronous dispatcher, so no Qt event loop is required.

## Configuration

Config lives outside the package so it survives upgrades:

```
%APPDATA%\ScholarPath\config.toml      # Windows
~/ScholarPath/config.toml              # other platforms
```

- `SCHOLARPATH_HOME` overrides the folder (handy for tests and portable setups).
- `--config <path>` points at a specific file.
- Template: [`config.example.toml`](config.example.toml) — contains no credentials.

```toml
[gateway]
provider = "stub"     # "opencode" arrives in Milestone 2
model = ""
timeout_seconds = 30.0
retries = 1

[ui]
theme = "dark"
window_width = 1100
window_height = 720

log_level = "INFO"
```

Invalid configuration is reported and the app exits with code `2`. A provider
that is configured but not implemented exits with code `3` — it never silently
falls back to the stub.

## Layout

```
src/scholarpath/
  app.py               entry point, argument parsing, startup checks
  config.py            pydantic config models, loading, template install
  logging_setup.py     console + rotating file logging (no payloads)
  gateway/base.py      provider-neutral types, errors, ModelGateway protocol
  gateway/stub.py      offline deterministic gateway (Milestone 1)
  gateway/factory.py   config -> gateway, explicit and honest
  ui/chat_controller.py conversation state + background execution
  ui/main_window.py    Qt window, transcript, input, status
tests/                 config, gateway, controller
```

Design rules in force: business logic never imports a provider SDK, failures are
typed and surfaced (never swallowed), and logs carry no message bodies or secrets.

## Logs

`%APPDATA%\ScholarPath\logs\scholarpath.log` (rotating, 3 × 1 MB).

## Limits of this milestone

| Works | Not built yet |
| ----- | ------------- |
| Launch, config, chat, error surfaces | Real models, web research, OCR, profiles, eligibility, ranking, MCP, packaging |

Next: Milestone 2 — OpenCode gateway adapter, model registry, task routing
([`goals.md`](goals.md) G202).
