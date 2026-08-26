import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


VALID_STATUSES = {"PENDING", "PROCESSING", "FINISHED", "SKIPPED", "ERROR"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class DB:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(self.path)
        self.cx.row_factory = sqlite3.Row
        self.cx.execute("PRAGMA foreign_keys = ON")
        self.cx.execute("PRAGMA journal_mode = WAL")
        self._ensure_schema()
        self.last_ranking = []

    def _ensure_schema(self):
        self.cx.execute("""
            CREATE TABLE IF NOT EXISTS queue(
                serial INTEGER PRIMARY KEY,
                selected_video_id TEXT UNIQUE,
                selected_video_title TEXT NOT NULL,
                selected_video_url TEXT NOT NULL,
                original_json TEXT NOT NULL,
                selected_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                error TEXT,
                metadata_json TEXT,
                final_path TEXT,
                final_json_path TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cx.execute("""
            CREATE TABLE IF NOT EXISTS skipped(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial INTEGER,
                original_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cx.execute("""
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial INTEGER,
                stage TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add columns to databases produced by older project versions.
        columns = {
            row["name"]
            for row in self.cx.execute("PRAGMA table_info(queue)").fetchall()
        }
        additions = {
            "final_json_path": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                self.cx.execute(f"ALTER TABLE queue ADD COLUMN {name} {definition}")

        self.cx.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_selected_video
            ON queue(selected_video_id)
        """)
        self.cx.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_status
            ON queue(status)
        """)
        self.cx.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_serial
            ON events(serial)
        """)
        self.cx.commit()

    def close(self):
        self.cx.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _next_serial(self):
        row = self.cx.execute(
            "SELECT COALESCE(MAX(serial), 0) + 1 AS serial FROM queue"
        ).fetchone()
        return int(row["serial"])

    def get(self, serial):
        return self.cx.execute(
            "SELECT * FROM queue WHERE serial=?",
            (int(serial),),
        ).fetchone()

    def get_or_create_serial(self, selected):
        row = self.cx.execute(
            "SELECT serial FROM queue WHERE selected_video_id=?",
            (selected["id"],),
        ).fetchone()
        if row:
            return int(row["serial"])

        serial = self._next_serial()
        now = utc_now()
        self.cx.execute("""
            INSERT INTO queue(
                serial,
                selected_video_id,
                selected_video_title,
                selected_video_url,
                original_json,
                selected_json,
                status,
                created_at,
                updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
        """, (
            serial,
            selected["id"],
            selected["title"],
            selected["url"],
            json.dumps({}, ensure_ascii=False),
            json.dumps(selected, ensure_ascii=False),
            "PENDING",
            now,
            now,
        ))
        self.cx.commit()
        return serial

    def set_selected(self, serial, original, selected):
        self.cx.execute("""
            UPDATE queue SET
                selected_video_id=?,
                selected_video_title=?,
                selected_video_url=?,
                original_json=?,
                selected_json=?,
                error=NULL,
                updated_at=?
            WHERE serial=?
        """, (
            selected["id"],
            selected["title"],
            selected["url"],
            json.dumps(original, ensure_ascii=False),
            json.dumps(selected, ensure_ascii=False),
            utc_now(),
            int(serial),
        ))
        self.cx.commit()

    def selected_exists(self, video_id, exclude_serial=None):
        if exclude_serial is None:
            row = self.cx.execute("""
                SELECT serial FROM queue
                WHERE selected_video_id=? AND status IN ('FINISHED','DONE')
                LIMIT 1
            """, (video_id,)).fetchone()
        else:
            row = self.cx.execute("""
                SELECT serial FROM queue
                WHERE selected_video_id=? AND status IN ('FINISHED','DONE') AND serial<>?
                LIMIT 1
            """, (video_id, int(exclude_serial))).fetchone()
        return int(row["serial"]) if row else None

    def set_status(self, serial, status, error=None):
        status = str(status).upper()
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid database status: {status}")
        self.cx.execute("""
            UPDATE queue
            SET status=?, error=?, updated_at=?
            WHERE serial=?
        """, (status, error, utc_now(), int(serial)))
        self.cx.commit()

    def finish(self, serial, metadata, final_path, final_json_path):
        self.cx.execute("""
            UPDATE queue SET
                status=?,
                error=NULL,
                metadata_json=?,
                final_path=?,
                final_json_path=?,
                updated_at=?
            WHERE serial=?
        """, (
            "FINISHED",
            json.dumps(metadata, ensure_ascii=False, default=str),
            str(final_path),
            str(final_json_path),
            utc_now(),
            int(serial),
        ))
        self.cx.commit()

    def record_skip(self, original, reason, serial=None):
        self.cx.execute("""
            INSERT INTO skipped(serial, original_json, reason)
            VALUES(?,?,?)
        """, (
            serial,
            json.dumps(original, ensure_ascii=False),
            reason,
        ))
        if serial is not None and self.get(serial):
            self.set_status(serial, "SKIPPED", reason)
        else:
            self.cx.commit()

    def reset(self, serial):
        if not self.get(serial):
            raise ValueError(f"Serial {serial} was not found.")
        self.set_status(serial, "PENDING", None)

    def event(self, serial, stage, message):
        self.cx.execute("""
            INSERT INTO events(serial, stage, message)
            VALUES(?,?,?)
        """, (serial, stage, message))
        self.cx.commit()
