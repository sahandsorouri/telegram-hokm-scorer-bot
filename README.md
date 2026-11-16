<img src="https://raw.githubusercontent.com/sahandsorouri/sahandsorouri/main/assets/banner.svg" alt="Sahand Sorouri" width="100%">

# Hokm Bot

A Telegram bot that keeps score for the Persian card game Hokm in group chats, with fixed red and blue teams and automatic hakem and kot tracking.

Live: [@Hokmnightsbot](https://t.me/Hokmnightsbot)

## What it does

- Records normal wins and kots, with a quick undo.
- Rotating kot: a kot that pushes a team past 7 wraps the score around instead of ending the game (6 + 3 = 9 becomes 2), and each team's lifetime count is shown.
- Pause button: stops the clock when a game is left halfway; paused time is not counted.
- Late-night games: anything before 6 AM counts as the previous day.
- Daily history and all-time totals, plus import of old games from one-line summaries.

## Commands

| Command | Action |
|---------|--------|
| `/newgame` | Start a new game (first to 7 points) |
| `/score` | Show the scoreboard again |
| `/stats` | Daily history and totals |
| `/undo` | Undo the last hand (up to 5 minutes after a game ends) |
| `/endgame` | End the current game |
| `/import` | Import old games |
| `/help` | Show help |

## Run

Copy `.env.example` to `.env` and set `BOT_TOKEN` (from [BotFather](https://t.me/BotFather)), then:

```bash
docker compose up -d --build
```

Game data is kept as JSON in `./data`, with automatic backups. To run it with systemd instead of Docker, see `deploy/deploy.sh`.

## Tech

Python, python-telegram-bot, JSON storage with asyncio locks, Docker or systemd.

---

Built by [Sahand Sorouri](https://sahand.sorouri.com) · platforms, bots and AI tools for businesses in Dubai.
