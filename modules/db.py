import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class DB:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(self.path)
        self.cx.row_factory = sqlite3.Row
        self._migrate_queue()
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
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        self.cx.execute("""
        CREATE TABLE IF NOT EXISTS skipped(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_json TEXT NOT NULL,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        self.cx.execute("""
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial INTEGER,
            stage TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        self.cx.commit()
        self.last_ranking = []

    def _migrate_queue(self):
        """Upgrade the previous queue schema without deleting old data."""
        try:
            cols = [r["name"] for r in self.cx.execute("PRAGMA table_info(queue)").fetchall()]
        except sqlite3.OperationalError:
            cols = []
        if cols and "original_json" not in cols:
            self.cx.execute("ALTER TABLE queue RENAME TO queue_legacy")
            self.cx.commit()

    def _next_serial(self):
        row = self.cx.execute("SELECT COALESCE(MAX(serial),0)+1 AS n FROM queue").fetchone()
        return int(row["n"])

    def get_or_create_serial(self, selected):
        row = self.cx.execute(
            "SELECT serial FROM queue WHERE selected_video_id=?",
            (selected["id"],),
        ).fetchone()
        if row:
            return int(row["serial"])
        serial = self._next_serial()
        self.cx.execute("""
            INSERT INTO queue(
                serial, selected_video_id, selected_video_title, selected_video_url,
                original_json, selected_json, status
            ) VALUES(?,?,?,?,?,?,?)
        """, (
            serial,
            selected["id"],
            selected["title"],
            selected["url"],
            json.dumps({}, ensure_ascii=False),
            json.dumps(selected, ensure_ascii=False),
            "PENDING",
        ))
        self.cx.commit()
        return serial

    def get(self, serial):
        return self.cx.execute("SELECT * FROM queue WHERE serial=?", (serial,)).fetchone()

    def set_selected(self, serial, original, selected):
        self.cx.execute("""
            UPDATE queue SET
              selected_video_id=?,
              selected_video_title=?,
              selected_video_url=?,
              original_json=?,
              selected_json=?,
              updated_at=CURRENT_TIMESTAMP
            WHERE serial=?
        """, (
            selected["id"], selected["title"], selected["url"],
            json.dumps(original, ensure_ascii=False),
            json.dumps(selected, ensure_ascii=False),
            serial,
        ))
        self.cx.commit()

    def selected_exists(self, video_id, exclude_serial=None):
        if exclude_serial is None:
            row = self.cx.execute(
                "SELECT 1 FROM queue WHERE selected_video_id=? AND status='FINISHED'",
                (video_id,),
            ).fetchone()
        else:
            row = self.cx.execute(
                "SELECT 1 FROM queue WHERE selected_video_id=? AND status='FINISHED' AND serial<>?",
                (video_id, exclude_serial),
            ).fetchone()
        return row is not None

    def set_status(self, serial, status, error=None):
        self.cx.execute(
            "UPDATE queue SET status=?,error=?,updated_at=CURRENT_TIMESTAMP WHERE serial=?",
            (status, error, serial),
        )
        self.cx.commit()

    def finish(self, serial, metadata, final):
        self.cx.execute("""
            UPDATE queue SET status='FINISHED', error=NULL, metadata_json=?,
            final_path=?, updated_at=CURRENT_TIMESTAMP WHERE serial=?
        """, (
            json.dumps(metadata, ensure_ascii=False, default=str),
            str(final),
            serial,
        ))
        self.cx.commit()

    def reset(self, serial):
        self.set_status(serial, "PENDING", None)

    def record_skip(self, original, reason):
        self.cx.execute(
            "INSERT INTO skipped(original_json,reason) VALUES(?,?)",
            (json.dumps(original, ensure_ascii=False), reason),
        )
        self.cx.commit()

    def event(self, serial, stage, message):
        self.cx.execute(
            "INSERT INTO events(serial,stage,message) VALUES(?,?,?)",
            (serial, stage, message),
        )
        self.cx.commit()
