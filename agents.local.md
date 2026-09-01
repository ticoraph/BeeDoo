# Reachy Mini Local Configuration

## Setup Status
Setup complete: YES

## User Environment
- Robot type: Lite (USB, full laptop compute)
- OS: macOS (darwin)
- Shell: zsh
- Python env tool: venv (standard, not uv)
- Resources path: this repo (BeeDoo) — SDK source lives in ./reachy_mini (git submodule tracking pollen-robotics/reachy_mini upstream, read-only)
- Python venv: ./.venv (reachy-mini SDK installed via pip, see requirements.txt)

## Notes for Future Sessions
- BeeDoo repo IS the robot's project repo (robot's name is BeeDoo).
- `./reachy_mini` submodule = official SDK source/docs/examples, read-only mirror of upstream (no fork, no push access).
- A separate official desktop app "Reachy Mini Control.app" is also installed on this Mac
  (~/Library/Application Support/com.pollen-robotics.reachy-mini). Its daemon competes for port 8000 —
  don't run both daemons at once.
- No app created yet. Follow reachy_mini/AGENTS.md workflow: write plan.md before coding,
  use `reachy-mini-app-assistant create` (never hand-create app folders).
- Default to JS/Web app flavour unless Python-specific need (per reachy_mini/AGENTS.md), but confirm with user first.
