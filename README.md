# Hokm Bot

Telegram bot for scoring the Persian card game **Hokm** in group chats. Fixed red and blue teams, automatic hakem and kot tracking.

Live: [@Hokmnightsbot](https://t.me/Hokmnightsbot)

## What it does

- Record normal wins, kot, and quick undo
- Rotating kot: a kot that pushes a team past 7 wraps the score around instead of ending the game (6 + 3 = 9 becomes 2), and each team's lifetime count is reported
- Smart game day: before 6 AM counts as the previous day (for late-night games)
- Daily history plus all-time totals
- Import old games from one-line summaries
- JSON storage with auto backup, asyncio locks, systemd restart

## Commands

| Command | Action |
|---------|--------|
| `/newgame` | Start a new game (first to 7 points) |
| `/score` | Resend the scoreboard |
| `/stats` | Daily history and totals |
| `/undo` | Undo last hand (works up to 5 minutes after a game ends) |

## Stack

`Python` `python-telegram-bot` `JSON storage` `Docker`

## Run

Set `TELEGRAM_BOT_TOKEN` in the environment:

```bash
docker compose up --build
```

## About

Built by [Sahand Sorouri](https://github.com/sahandsorouri).
