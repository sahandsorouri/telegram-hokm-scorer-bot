"""Add a retroactive pause to one archived game that was left open for a long time.

Before the pause button existed (shipped 2026-11-10), a game that was abandoned
mid-way and finished days later was logged with its full wall-clock length. This
script marks the long idle gap of such a game as a pause, so its duration and the
lifetime time stats only count real play time.

It only ADDS fields to the record (pauses, paused_seconds, game_day_started) and
moves game_day to the day the game was finished. started_at, ended_at and the
hands are never touched. It is a dry run unless --apply is given, it writes a
timestamped copy of the state file first, and it refuses to run twice.

    python scripts/fix_unpaused_game.py --chat -5133399850 \
        --started-at 2026-11-08T01:18:01.273570+03:30 [--apply]

Run it while the bot is stopped, so nothing else writes the state file.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import game  # noqa: E402

MIN_GAP_SECONDS = 3 * 3600  # only a gap longer than this is treated as "left the game"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", required=True)
    ap.add_argument("--started-at", required=True)
    ap.add_argument("--data-dir", default=str(Path(__file__).resolve().parent.parent / "data"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    data = Path(a.data_dir)
    state_path = data / f"{a.chat}.json"
    events_path = data / f"{a.chat}.events.jsonl"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    matches = [r for r in state["history"] if r.get("started_at") == a.started_at]
    if len(matches) != 1:
        print(f"expected exactly 1 record with that started_at, found {len(matches)}")
        return 1
    rec = matches[0]
    if rec.get("pauses") or rec.get("paused_seconds"):
        print("record already has pause data, nothing to do")
        return 0

    start = datetime.fromisoformat(rec["started_at"])
    end = datetime.fromisoformat(rec["ended_at"])

    # Hand times of this game, from the append-only event log.
    times = [start]
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("type") != "hand":
            continue
        t = datetime.fromisoformat(e["ts"])
        if start <= t <= end + timedelta(seconds=1):
            times.append(t)
    if len(times) - 1 != rec.get("hands_count"):
        print(f"event log has {len(times) - 1} hands, record says {rec.get('hands_count')}: stopping")
        return 1

    gaps = [(times[i] - times[i - 1]).total_seconds() for i in range(1, len(times))]
    long_i = max(range(len(gaps)), key=lambda i: gaps[i])
    if gaps[long_i] < MIN_GAP_SECONDS:
        print("no gap longer than 3 hours in this game, nothing to do")
        return 0
    if sum(1 for g in gaps if g >= MIN_GAP_SECONDS) != 1:
        print("more than one long gap, handle this game by hand")
        return 1
    others = [g for i, g in enumerate(gaps) if i != long_i]
    avg_hand = sum(others) / len(others) if others else 0.0

    # The hand that ended the gap also took some play time. We do not know how
    # much, so it gets this game's average hand length; the rest is the pause.
    pause_from = times[long_i]
    pause_to = times[long_i + 1] - timedelta(seconds=min(avg_hand, gaps[long_i]))
    pause = {
        "from": pause_from.isoformat(),
        "to": pause_to.isoformat(),
        "retro": True,
        "note": "added 2026-11-10: game was left open before the pause button existed",
    }
    paused = game.paused_seconds([pause])
    old_dur = (end - start).total_seconds()
    new_day = game.game_day(end)

    print(f"record:        {rec['game_day']}  {rec['started_at']} -> {rec['ended_at']}")
    print(f"old duration:  {old_dur / 3600:.2f} h")
    print(f"pause:         {pause['from']} -> {pause['to']}  ({paused / 3600:.2f} h)")
    print(f"new duration:  {(old_dur - paused) / 60:.1f} min  (avg hand {avg_hand / 60:.1f} min)")
    print(f"game_day:      {rec['game_day']} -> {new_day}")

    if not a.apply:
        print("dry run, nothing written (add --apply)")
        return 0

    backup = state_path.with_name(f"{state_path.name}.pre-pause-fix.{int(time.time())}")
    backup.write_bytes(state_path.read_bytes())

    rec["pauses"] = [pause]
    rec["paused_seconds"] = paused
    if new_day != rec["game_day"]:
        rec["game_day_started"] = rec["game_day"]
        rec["game_day"] = new_day

    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(state_path)

    with open(events_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": game.now_tz().isoformat(),
            "type": "retro_pause",
            "game_started_at": rec["started_at"],
            "pause": pause,
            "paused_seconds": paused,
            "game_day_from": rec.get("game_day_started"),
            "game_day_to": rec["game_day"],
        }, ensure_ascii=False) + "\n")

    print(f"applied. backup: {backup.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
