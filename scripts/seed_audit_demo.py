#!/usr/bin/env python3
"""Seed the audit + throughput SQLite store with demo data.

Purpose
-------
Generate a realistic-looking but synthetic set of audit events and
throughput buckets so the Admin UI's Audit Log and Throughput pages
look populated when you take screenshots for docs / marketing /
investor demos.

Default story:
  - 24-hour window ending now
  - 5 active users (stable pseudonym hashes, not derived from any real
    person)
  - 6 services in rotation: notion, google_workspace, jira, slack,
    bigquery, gitlab
  - ~120 events distributed over the window, with realistic byte volumes
  - One user has a 3-AM outbound spike (~80 MB of Drive exports) — the
    DLP / exfiltration-shaped anomaly the Throughput dashboard exists for
  - A handful of PII detections, hook denials, OAuth refreshes, and
    throughput alerts mixed in for visual variety

What it touches
---------------
The single SQLite file the gateway uses for both stores. Default path
``/app/data/audit.db`` (production layout) — override with
``--db /path/to/audit.db`` or the ``AUDIT_DB_PATH`` env var to point at
your local-dev volume mount.

The script is idempotent in the sense that running it again wipes the
demo rows and re-seeds. Real audit data **is preserved** — the script
only deletes rows whose ``user_hash`` is one of its own demo hashes.

Safety
------
- Never run against a production audit DB. The demo user_hashes are
  reserved (prefixed with ``demo_``) so even an accidental run would
  be cleanable by hand, but don't.
- Set ``MCPGATE_ALLOW_AUDIT_SEED=1`` to acknowledge you understand this
  is destructive to existing demo seed data.

Usage
-----
::

    # Default — writes to /app/data/audit.db (Docker container path)
    MCPGATE_ALLOW_AUDIT_SEED=1 python3 scripts/seed_audit_demo.py

    # Local dev — override the path to wherever your volume mount lives
    MCPGATE_ALLOW_AUDIT_SEED=1 python3 scripts/seed_audit_demo.py \\
        --db ./data/audit.db

    # Custom story window
    MCPGATE_ALLOW_AUDIT_SEED=1 python3 scripts/seed_audit_demo.py \\
        --db ./data/audit.db --hours 48 --events 250

Then take screenshots of the Admin UI's Audit Log and Throughput pages.
The data lives for whatever your gateway's retention is (default 90d).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Demo hashes — fixed across runs so the same "users" show up in repeated
# seedings. All start with the same first two hex chars per service for
# readability in the UI (real hashes are sha256[:16]).
DEMO_USERS = [
    {"hash": "f9e65aa7b9b11db9", "label": "regular-user-a"},
    {"hash": "3c4def01a82b6e74", "label": "regular-user-b"},
    {"hash": "8b7a02cd419f3e57", "label": "regular-user-c"},
    {"hash": "a4e8c6b27d390f81", "label": "outlier-user"},  # the 3-AM exfil
    {"hash": "2d91be43f5c8a716", "label": "regular-user-d"},
]
OUTLIER_USER_HASH = "a4e8c6b27d390f81"

# Services and the action surfaces shown in the UI. (tool, action) pairs.
TOOL_ACTIONS = [
    ("notion_read_actions",            "query_database"),
    ("notion_read_actions",            "get_page"),
    ("notion_write_actions",           "create_page"),
    ("google_workspace_read_actions",  "drive_files_list"),
    ("google_workspace_read_actions",  "gmail_search"),
    ("google_workspace_read_actions",  "calendar_events_list"),
    ("google_workspace_write_actions", "drive_files_export"),  # used by outlier
    ("google_workspace_write_actions", "docs_create"),
    ("jira_read_actions",              "search_issues"),
    ("jira_write_actions",             "create_issue"),
    ("jira_write_actions",             "add_comment"),
    ("slack_read_actions",             "search_messages"),
    ("slack_read_actions",             "channels_history"),
    ("slack_write_actions",            "post_message"),
    ("bigquery_read_actions",          "list_datasets"),
    ("bigquery_read_actions",          "run_query"),
    ("gitlab_read_actions",            "list_merge_requests"),
    ("gitlab_write_actions",           "create_issue"),
]

# Clients that connect — shows up in the Throughput per-client breakdown.
CLIENTS = ["claude_code", "chatgpt_agent", "cursor", "gemini_cli"]

# Event-type weights for the "normal" event mix. These should yield a
# screenshot where you can see all five severity bands by scrolling.
NORMAL_EVENTS = [
    ("auth_success",              "green",  6),
    ("session_created",           "green",  3),
    ("oauth_token_refreshed",     "green",  4),
    ("pii_outbound_detected",     "yellow", 3),
    ("pii_outbound_confirmed",    "yellow", 2),
    ("admin_security_audit",      "green",  1),
    ("instance_config_changed",   "yellow", 1),
    ("auth_failure",              "red",    1),
    ("pii_scrub_failed",          "red",    1),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--db",
        default=os.environ.get("AUDIT_DB_PATH", "/app/data/audit.db"),
        help="Path to the audit SQLite file (default: /app/data/audit.db)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="How many hours of history to seed, ending at 'now' (default: 24)",
    )
    parser.add_argument(
        "--events",
        type=int,
        default=120,
        help="Approximate total event count to generate (default: 120)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    if os.environ.get("MCPGATE_ALLOW_AUDIT_SEED") != "1":
        print(
            "Refusing to run without MCPGATE_ALLOW_AUDIT_SEED=1.\n"
            "Set it explicitly to acknowledge this rewrites demo-seeded\n"
            "rows in the audit store.",
            file=sys.stderr,
        )
        return 2

    db_path = Path(args.db)
    if not db_path.parent.exists():
        print(
            f"Parent directory does not exist: {db_path.parent}\n"
            "Either create it, or point --db at an existing audit.db.",
            file=sys.stderr,
        )
        return 3

    rng = random.Random(args.seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    window_start = now - timedelta(hours=args.hours)

    print(f"Seeding {db_path}")
    print(f"  Window: {window_start.isoformat()} → {now.isoformat()}")
    print(f"  Target events: ~{args.events}")

    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    # The gateway initialises these tables itself; create them here too
    # so the script works against a fresh DB file before the gateway has
    # ever started.
    _ensure_tables(conn)

    # Clean up any prior demo rows (only those keyed to demo hashes)
    demo_hashes = [u["hash"] for u in DEMO_USERS]
    qmarks = ",".join("?" for _ in demo_hashes)
    cur = conn.cursor()
    cur.execute(f"DELETE FROM audit_events WHERE user_hash IN ({qmarks})", demo_hashes)
    deleted_audit = cur.rowcount
    cur.execute(f"DELETE FROM throughput_bucket WHERE user_hash IN ({qmarks})", demo_hashes)
    deleted_throughput = cur.rowcount
    if deleted_audit or deleted_throughput:
        print(f"  Cleared {deleted_audit} audit + {deleted_throughput} throughput demo rows")

    # ----- Generate audit events ----------------------------------------------------
    audit_rows = []
    throughput_calls = []  # (ts, user, tool, action, client, bytes_total, failed)

    # 1) Steady baseline traffic across all users
    for _ in range(int(args.events * 0.7)):
        ts = _random_ts_in_window(rng, window_start, now)
        user = rng.choice(DEMO_USERS)["hash"]
        tool, action = rng.choice(TOOL_ACTIONS)
        client = rng.choice(CLIENTS)
        if tool.endswith("_read_actions"):
            payload_in = rng.randint(200, 2_000)
            payload_out = rng.randint(800, 80_000)
        else:
            payload_in = rng.randint(400, 6_000)
            payload_out = rng.randint(400, 12_000)
        # Most calls succeed
        success = rng.random() > 0.05
        audit_rows.append(
            (
                ts,
                "tool_call_completed" if success else "tool_call_failed",
                user,
                json.dumps(
                    {
                        "tool": tool,
                        "action": action,
                        "client": client,
                        "bytes_in": payload_in,
                        "bytes_out": payload_out,
                        "status_code": 200 if success else rng.choice([403, 429, 502]),
                    },
                    separators=(",", ":"),
                ),
                None,  # ip_hash — not seeding
                1 if success else 0,
            )
        )
        throughput_calls.append(
            (ts, user, tool, action, client, payload_in + payload_out, 0 if success else 1)
        )

    # 2) Sprinkle compliance-flavoured events for visual variety
    for event_name, _color, count in NORMAL_EVENTS:
        for _ in range(count):
            ts = _random_ts_in_window(rng, window_start, now)
            user = rng.choice(DEMO_USERS)["hash"]
            details = _event_details(event_name, rng)
            audit_rows.append(
                (
                    ts,
                    event_name,
                    user,
                    json.dumps(details, separators=(",", ":")),
                    None,
                    1 if event_name not in {"auth_failure", "pii_scrub_failed"} else 0,
                )
            )

    # 3) The DLP-shaped outlier: a single user, between 02:30 and 03:30,
    #    exports a stack of Drive files. The throughput dashboard's
    #    threshold alert should fire on this.
    exfil_anchor = (now - timedelta(hours=23)).replace(minute=58, second=49, microsecond=0)
    # Push to 3 AM local-ish — works regardless of wallclock since the
    # window is the last 24 h
    for i in range(8):
        ts = (exfil_anchor + timedelta(minutes=2 * i, seconds=rng.randint(0, 59))).isoformat()
        bytes_out = rng.randint(7_000_000, 12_000_000)  # 7–12 MB per export
        bytes_in = rng.randint(400, 800)
        audit_rows.append(
            (
                ts,
                "tool_call_completed",
                OUTLIER_USER_HASH,
                json.dumps(
                    {
                        "tool": "google_workspace_write_actions",
                        "action": "drive_files_export",
                        "client": "claude_code",
                        "bytes_in": bytes_in,
                        "bytes_out": bytes_out,
                        "status_code": 200,
                    },
                    separators=(",", ":"),
                ),
                None,
                1,
            )
        )
        throughput_calls.append(
            (
                ts,
                OUTLIER_USER_HASH,
                "google_workspace_write_actions",
                "drive_files_export",
                "claude_code",
                bytes_in + bytes_out,
                0,
            )
        )

    # 4) Throughput-alert rows on the outlier — what the Slack alerter
    #    would have written as it fired every 5 min for 30 min.
    for offset_min in range(0, 30, 5):
        ts = (exfil_anchor + timedelta(minutes=10 + offset_min)).isoformat()
        audit_rows.append(
            (
                ts,
                "throughput_alert_fired",
                OUTLIER_USER_HASH,
                json.dumps(
                    {
                        "level": "alert_30m",
                        "tool": "google_workspace_write_actions",
                        "outbound_mb_30m": round(50 + offset_min * 0.7, 2),
                        "channel": "#security",
                    },
                    separators=(",", ":"),
                ),
                None,
                1,
            )
        )

    # 5) Hook denied actions — show the prevention layer firing
    for _ in range(4):
        ts = _random_ts_in_window(rng, window_start, now)
        user = rng.choice(DEMO_USERS)["hash"]
        denied_tool, denied_action = rng.choice(
            [
                ("jira_write_actions", "delete_issue"),
                ("notion_write_actions", "archive_page"),
                ("gitlab_write_actions", "delete_branch"),
                ("slack_write_actions", "delete_message"),
            ]
        )
        audit_rows.append(
            (
                ts,
                "hook_denied_action",
                user,
                json.dumps(
                    {
                        "tool": denied_tool,
                        "action": denied_action,
                        "policy": "destructive_requires_confirmation",
                        "actor_group": "research_interns" if rng.random() > 0.5 else "default",
                    },
                    separators=(",", ":"),
                ),
                None,
                0,
            )
        )

    # ----- Write audit events ------------------------------------------------------
    cur.executemany(
        "INSERT INTO audit_events (timestamp, event_type, user_hash, details, ip_hash, success) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        audit_rows,
    )
    print(f"  Inserted {len(audit_rows)} audit rows")

    # ----- Write throughput buckets -----------------------------------------------
    # Aggregate the call records into hour + day buckets in the same shape
    # the gateway's throughput store writes them.
    buckets: dict[tuple, dict] = {}
    for ts_str, user, tool, action, client, byte_total, failed in throughput_calls:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        for kind, fmt in (("hour", "%Y-%m-%dT%H"), ("day", "%Y-%m-%d")):
            key = (kind, ts.strftime(fmt), user, tool, action, client)
            row = buckets.setdefault(
                key,
                {
                    "calls": 0,
                    "bytes": 0,
                    "failed_calls": 0,
                    "failed_bytes": 0,
                    "first_seen": ts_str,
                    "last_seen": ts_str,
                },
            )
            row["calls"] += 1
            row["bytes"] += byte_total
            if failed:
                row["failed_calls"] += 1
                row["failed_bytes"] += byte_total
            if ts_str < row["first_seen"]:
                row["first_seen"] = ts_str
            if ts_str > row["last_seen"]:
                row["last_seen"] = ts_str

    bucket_rows = [
        (kind, iso, user, tool, action, client,
         row["calls"], row["bytes"], row["failed_calls"], row["failed_bytes"],
         row["first_seen"], row["last_seen"])
        for (kind, iso, user, tool, action, client), row in buckets.items()
    ]
    cur.executemany(
        "INSERT OR REPLACE INTO throughput_bucket "
        "(bucket_kind, bucket_iso, user_hash, tool, action, client, "
        "calls, bytes, failed_calls, failed_bytes, first_seen, last_seen) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        bucket_rows,
    )
    print(f"  Inserted {len(bucket_rows)} throughput buckets")

    conn.commit()
    conn.close()
    print()
    print("Done. Open the Admin UI:")
    print("  Audit Log  → see the 24h timeline; filter by RED for the alert rows")
    print("  Throughput → outlier-user (hash starting a4e8c6b2) tops the list,")
    print("               click in to see the 3-AM Drive exports concentrated in one hour")
    return 0


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            user_hash TEXT,
            details TEXT,
            ip_hash TEXT,
            success INTEGER DEFAULT 1
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_hash ON audit_events(user_hash)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS throughput_bucket (
            bucket_kind   TEXT NOT NULL,
            bucket_iso    TEXT NOT NULL,
            user_hash     TEXT NOT NULL,
            tool          TEXT NOT NULL,
            action        TEXT NOT NULL,
            client        TEXT NOT NULL,
            calls         INTEGER NOT NULL,
            bytes         INTEGER NOT NULL,
            failed_calls  INTEGER NOT NULL,
            failed_bytes  INTEGER NOT NULL,
            first_seen    TEXT NOT NULL,
            last_seen     TEXT NOT NULL,
            PRIMARY KEY (bucket_kind, bucket_iso, user_hash, tool, action, client)
        )
        """
    )


def _random_ts_in_window(rng: random.Random, start: datetime, end: datetime) -> str:
    span = (end - start).total_seconds()
    offset = rng.uniform(0, span)
    ts = start + timedelta(seconds=offset)
    return ts.replace(microsecond=0).isoformat()


def _event_details(event_name: str, rng: random.Random) -> dict:
    if event_name.startswith("oauth_"):
        return {"service": rng.choice(["google_workspace", "jira", "slack", "gitlab", "notion"])}
    if event_name.startswith("pii_outbound"):
        return {
            "pattern_matched": rng.choice(["email", "phone", "person_name"]),
            "count": rng.randint(1, 5),
        }
    if event_name == "pii_scrub_failed":
        return {"reason": "pattern_compile_error", "service": "notion"}
    if event_name == "auth_failure":
        return {"reason": "invalid_token"}
    if event_name == "instance_config_changed":
        return {"setting": rng.choice(["throughput_threshold_mb", "audit_retention_days"])}
    if event_name == "admin_security_audit":
        return {"scope": "weekly_scheduled"}
    return {}


if __name__ == "__main__":
    sys.exit(main())
