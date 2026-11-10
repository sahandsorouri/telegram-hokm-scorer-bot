# Hokm Bot — Backlog

Small enhancements. Mostly stats surfaced in the end-of-game report and `/stats`.

## Stats in the end-of-game report

- [ ] **Win share per team** — show what percentage of hands each team won (Red vs Blue), in the end-of-game report.
- [ ] **Which night of the game** — show the night number ("night N") for the current game.
- [ ] **Nights since tournament start** — show how many nights have elapsed since the tournament/season began.
- [ ] **Total days played** — derive from the logs and show total number of distinct play-days.

## Done

- [x] **Pause button**: `⏸ توقف` on the scoreboard stops the clock, `▶️ ادامه بازی` restarts it; paused time is left out of the game's duration and the lifetime time stats. Shipped 2026-11-10, with a one-off fix for the 7 to 10 Nov game that sat open for 67 hours.

- [x] **Rotating kot count per team** — kots that pushed the score past 7 and wrapped it around. Shipped 2026-08-28 (`c4ec135`): lifetime line in the end-of-game report and `/stats`, plus a this-game callout when one happens.

## Notes

- Source of these ideas: personal notes (Telegram saved messages), captured 2026-06-26.
- These are read-only/reporting features over existing stored results (JSON in `data/`), so likely small additions to `messages.py` formatting plus a couple of helpers in `game.py` / `storage.py`. "یه خط کد ریزه" — keep it tiny.
