# AGENTS.md

This repo is a Bitcoin PAPER-trading kit (`btcpaper`). Before doing anything trading-related, read the skill:
`.agents/skills/btc-paper/SKILL.md` (same file in `.github/skills/` and `.claude/skills/`).

Non-negotiable: paper only. No real orders, no exchange API keys, no live trading code. Run
`python -m btcpaper check` after touching any strategy and `python -m btcpaper test` after touching `btcpaper/`.
On Windows use `.venv\Scripts\python`.

## The live paper bot in this repo

`.github/workflows/paper-tick.yml` runs `live/tick.py` every ~15 min on GitHub Actions and publishes `docs/` (the
dashboard) to GitHub Pages. Accounts are defined in `live/accounts.json`; their state, trades, decisions and equity
are in `live/state/<account id>/` and are committed by the bot. Rules for changes:
- To change or add a strategy account, edit `live/accounts.json` (and add the strategy file in `strategies/`).
  Run `python -m btcpaper check` and `python live/tick.py` locally first; never edit files under `live/state/` by hand
  unless asked (a new account id starts a fresh account; deleting `live/state/<id>/` resets that one account).
- Pull before you push: the bot commits every ~15 minutes.
- Never add exchange API keys, secrets or order code. This bot is paper only.
