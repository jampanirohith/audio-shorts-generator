import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

VALID_STATUSES = {"PENDING", "PROCESSING", "FINISHED", "SKIPPED", "ERROR"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


class PlaylistDB:
    """Persistent source-of-truth for playlist membership, order and state."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(self.path, timeout=30)
        self.cx.row_factory = sqlite3.Row
        self.cx.execute("PRAGMA foreign_keys=ON")
        self.cx.execute("PRAGMA journal_mode=WAL")
        self.cx.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    def close(self):
        try:
            self.cx.execute("PRAGMA optimize")
        finally:
            self.cx.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _ensure_schema(self):
        self.cx.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS playlists(
            playlist_id TEXT PRIMARY KEY,
            playlist_url TEXT NOT NULL,
            title TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            last_run_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS playlist_runs(
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            entry_count INTEGER NOT NULL DEFAULT 0,
            added_count INTEGER NOT NULL DEFAULT 0,
            removed_count INTEGER NOT NULL DEFAULT 0,
            reordered_count INTEGER NOT NULL DEFAULT 0,
            changed_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(playlist_id) REFERENCES playlists(playlist_id)
        );

        CREATE TABLE IF NOT EXISTS playlist_entries(
            playlist_id TEXT NOT NULL,
            original_video_id TEXT NOT NULL,
            original_title TEXT NOT NULL,
            original_url TEXT NOT NULL,
            current_position INTEGER,
            previous_position INTEGER,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            current INTEGER NOT NULL DEFAULT 1,
            processing_status TEXT NOT NULL DEFAULT 'PENDING',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            completed_at TEXT,
            last_error TEXT,
            final_serial INTEGER,
            metadata_json TEXT,
            PRIMARY KEY(playlist_id, original_video_id),
            FOREIGN KEY(playlist_id) REFERENCES playlists(playlist_id)
        );

        CREATE TABLE IF NOT EXISTS playlist_entry_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            playlist_id TEXT NOT NULL,
            original_video_id TEXT NOT NULL,
            position INTEGER,
            title TEXT,
            url TEXT,
            event_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES playlist_runs(run_id),
            FOREIGN KEY(playlist_id) REFERENCES playlists(playlist_id)
        );

        CREATE INDEX IF NOT EXISTS idx_playlist_entries_status
            ON playlist_entries(processing_status);
        CREATE INDEX IF NOT EXISTS idx_playlist_entries_current
            ON playlist_entries(playlist_id, current, current_position);
        CREATE INDEX IF NOT EXISTS idx_playlist_history_video
            ON playlist_entry_history(playlist_id, original_video_id);
        """)

        self.cx.execute("""
            INSERT INTO schema_meta(key,value) VALUES('schema_version','2')
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """)
        self.cx.commit()

    @staticmethod
    def playlist_id_from_url(url):
        import re
        match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", str(url or ""))
        return match.group(1) if match else str(url)

    def sync(self, playlist_url, entries, playlist_title=None):
        playlist_id = self.playlist_id_from_url(playlist_url)
        now = utc_now()

        existing_playlist = self.cx.execute(
            "SELECT * FROM playlists WHERE playlist_id=?", (playlist_id,)
        ).fetchone()

        if existing_playlist:
            self.cx.execute("""
                UPDATE playlists
                SET playlist_url=?, title=COALESCE(?,title), last_seen_at=?
                WHERE playlist_id=?
            """, (playlist_url, playlist_title, now, playlist_id))
        else:
            self.cx.execute("""
                INSERT INTO playlists(
                    playlist_id,playlist_url,title,first_seen_at,last_seen_at
                ) VALUES(?,?,?,?,?)
            """, (playlist_id, playlist_url, playlist_title or "", now, now))

        self.cx.execute("""
            INSERT INTO playlist_runs(playlist_id,started_at,entry_count)
            VALUES(?,?,?)
        """, (playlist_id, now, len(entries)))
        run_id = self.cx.execute("SELECT last_insert_rowid()").fetchone()[0]

        old_rows = {
            row["original_video_id"]: row
            for row in self.cx.execute("""
                SELECT * FROM playlist_entries WHERE playlist_id=?
            """, (playlist_id,)).fetchall()
        }
        current_ids = {e["id"] for e in entries}
        added = removed = reordered = changed = 0

        for position, entry in enumerate(entries, 1):
            vid = entry["id"]
            old = old_rows.get(vid)
            title = entry.get("title", "")
            url = entry.get("url", "")
            if old is None:
                event = "ADDED"
                added += 1
                self.cx.execute("""
                    INSERT INTO playlist_entries(
                        playlist_id,original_video_id,original_title,original_url,
                        current_position,previous_position,first_seen_at,last_seen_at,
                        current,processing_status,metadata_json
                    ) VALUES(?,?,?,?,?,?,?,?,1,'PENDING',?)
                """, (
                    playlist_id, vid, title, url, position, None, now, now,
                    _json(entry),
                ))
            else:
                event = None
                if old["current"] and old["current_position"] != position:
                    event = "REORDERED"
                    reordered += 1
                if old["original_title"] != title or old["original_url"] != url:
                    if event is None:
                        event = "CHANGED"
                    changed += 1
                self.cx.execute("""
                    UPDATE playlist_entries SET
                        original_title=?, original_url=?,
                        previous_position=current_position,
                        current_position=?, last_seen_at=?, current=1,
                        metadata_json=?
                    WHERE playlist_id=? AND original_video_id=?
                """, (title, url, position, now, _json(entry),
                      playlist_id, vid))
            if event:
                self.cx.execute("""
                    INSERT INTO playlist_entry_history(
                        run_id,playlist_id,original_video_id,position,title,url,event_type,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                """, (run_id, playlist_id, vid, position, title, url, event, now))

        for vid, old in old_rows.items():
            if vid not in current_ids and old["current"]:
                removed += 1
                self.cx.execute("""
                    UPDATE playlist_entries
                    SET current=0, previous_position=current_position,
                        current_position=NULL, last_seen_at=?
                    WHERE playlist_id=? AND original_video_id=?
                """, (now, playlist_id, vid))
                self.cx.execute("""
                    INSERT INTO playlist_entry_history(
                        run_id,playlist_id,original_video_id,position,title,url,event_type,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                """, (
                    run_id, playlist_id, vid, old["current_position"],
                    old["original_title"], old["original_url"], "REMOVED", now
                ))

        self.cx.execute("""
            UPDATE playlist_runs SET finished_at=?, added_count=?,
                removed_count=?, reordered_count=?, changed_count=?
            WHERE run_id=?
        """, (utc_now(), added, removed, reordered, changed, run_id))
        self.cx.execute(
            "UPDATE playlists SET last_run_id=? WHERE playlist_id=?",
            (run_id, playlist_id)
        )
        self.cx.commit()

        rows = self.cx.execute("""
            SELECT * FROM playlist_entries
            WHERE playlist_id=? AND current=1
            ORDER BY current_position
        """, (playlist_id,)).fetchall()

        return playlist_id, run_id, rows, {
            "added": added, "removed": removed,
            "reordered": reordered, "changed": changed,
        }

    def set_status(self, playlist_id, video_id, status, *, serial=None, error=None):
        status = str(status).upper()
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid playlist status: {status}")
        now = utc_now()
        attempt_sql = ", attempt_count=attempt_count+1, last_attempt_at=?" if status == "PROCESSING" else ""
        params = [status]
        if status == "PROCESSING":
            params.append(now)
        params.extend([error, serial, now, playlist_id, video_id])
        self.cx.execute(f"""
            UPDATE playlist_entries
            SET processing_status=?{attempt_sql},
                last_error=?, final_serial=?, last_seen_at=?
            WHERE playlist_id=? AND original_video_id=?
        """, params)
        if status == "FINISHED":
            self.cx.execute("""
                UPDATE playlist_entries
                SET completed_at=?, last_error=NULL
                WHERE playlist_id=? AND original_video_id=?
            """, (now, playlist_id, video_id))
        self.cx.commit()

    def recover_processing(self):
        self.cx.execute("""
            UPDATE playlist_entries
            SET processing_status='ERROR',
                last_error=COALESCE(last_error,'Recovered stale PROCESSING state')
            WHERE processing_status='PROCESSING'
        """)
        self.cx.commit()

    def get(self, playlist_id, video_id):
        return self.cx.execute("""
            SELECT * FROM playlist_entries
            WHERE playlist_id=? AND original_video_id=?
        """, (playlist_id, video_id)).fetchone()

    def update_serial(self, playlist_id, video_id, serial):
        self.cx.execute("""
            UPDATE playlist_entries SET final_serial=? WHERE playlist_id=? AND original_video_id=?
        """, (int(serial), playlist_id, video_id))
        self.cx.commit()

    def current_entries(self, playlist_id):
        return self.cx.execute("""
            SELECT * FROM playlist_entries
            WHERE playlist_id=? AND current=1
            ORDER BY current_position
        """, (playlist_id,)).fetchall()

    def run_summary(self, run_id):
        return self.cx.execute(
            "SELECT * FROM playlist_runs WHERE run_id=?", (run_id,)
        ).fetchone()


class ReelDB:
    """Persistent source-of-truth for final reels; selected YouTube video is primary identity."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(self.path, timeout=30)
        self.cx.row_factory = sqlite3.Row
        self.cx.execute("PRAGMA foreign_keys=ON")
        self.cx.execute("PRAGMA journal_mode=WAL")
        self.cx.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()
        self._migrate_legacy_if_needed()

    def close(self):
        try:
            self.cx.execute("PRAGMA optimize")
        finally:
            self.cx.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _ensure_schema(self):
        self.cx.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta(
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reels(
            serial INTEGER PRIMARY KEY,
            selected_video_id TEXT NOT NULL UNIQUE,
            selected_video_title TEXT NOT NULL,
            selected_video_url TEXT NOT NULL,
            original_playlist_id TEXT,
            original_video_id TEXT,
            original_json TEXT NOT NULL,
            selected_json TEXT NOT NULL,
            search_json TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            error TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT,
            final_path TEXT,
            final_json_path TEXT,
            source_sha256 TEXT,
            final_sha256 TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS reel_selection_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial INTEGER NOT NULL,
            selected_video_id TEXT NOT NULL,
            selected_video_title TEXT NOT NULL,
            selected_video_url TEXT NOT NULL,
            mode TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(serial) REFERENCES reels(serial)
        );

        CREATE TABLE IF NOT EXISTS reel_skips(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial INTEGER,
            original_video_id TEXT,
            original_json TEXT,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reel_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial INTEGER,
            stage TEXT NOT NULL,
            message TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_reels_status ON reels(status);
        CREATE INDEX IF NOT EXISTS idx_reels_original ON reels(original_video_id);
        CREATE INDEX IF NOT EXISTS idx_events_serial ON reel_events(serial);
        CREATE INDEX IF NOT EXISTS idx_selection_history_serial ON reel_selection_history(serial);
        """)
        self.cx.execute("""
            INSERT INTO schema_meta(key,value) VALUES('schema_version','2')
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """)
        self.cx.commit()

    def _migrate_legacy_if_needed(self):
        """Import the previous single-database queue once, preserving serials and outputs."""
        count = self.cx.execute("SELECT COUNT(*) AS n FROM reels").fetchone()["n"]
        legacy = Path("state/pipeline.db")
        if count or not legacy.is_file() or legacy.resolve() == self.path.resolve():
            return
        try:
            old = sqlite3.connect(legacy, timeout=10)
            old.row_factory = sqlite3.Row
            tables = {
                r["name"] for r in old.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "queue" not in tables:
                old.close()
                return
            rows = old.execute("SELECT * FROM queue ORDER BY serial").fetchall()
            for row in rows:
                status = str(row["status"] or "PENDING").upper()
                if status == "DONE":
                    status = "FINISHED"
                if status not in VALID_STATUSES:
                    status = "ERROR"
                now = utc_now()
                original_json = row["original_json"] or _json({})
                selected_json = row["selected_json"] or _json({
                    "id": row["selected_video_id"],
                    "title": row["selected_video_title"],
                    "url": row["selected_video_url"],
                })
                try:
                    original_data = json.loads(original_json)
                except Exception:
                    original_data = {}
                self.cx.execute("""
                    INSERT OR IGNORE INTO reels(
                        serial,selected_video_id,selected_video_title,selected_video_url,
                        original_playlist_id,original_video_id,
                        original_json,selected_json,status,error,metadata_json,
                        final_path,final_json_path,created_at,updated_at,completed_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    int(row["serial"]), row["selected_video_id"],
                    row["selected_video_title"], row["selected_video_url"],
                    original_data.get("playlist_id"), original_data.get("id"),
                    original_json, selected_json, status, row["error"],
                    row["metadata_json"], row["final_path"], row["final_json_path"],
                    row["created_at"] or now, row["updated_at"] or now,
                    now if status == "FINISHED" else None,
                ))
            self.cx.commit()
            old.close()
        except Exception:
            # A failed migration must never prevent a clean new database from starting.
            # The legacy file remains untouched and can be inspected manually.
            self.cx.rollback()

    def _next_serial(self):
        row = self.cx.execute(
            "SELECT COALESCE(MAX(serial),0)+1 AS serial FROM reels"
        ).fetchone()
        return int(row["serial"])

    def get(self, serial):
        return self.cx.execute(
            "SELECT * FROM reels WHERE serial=?", (int(serial),)
        ).fetchone()

    def by_original_video_id(self, video_id):
        return self.cx.execute(
            "SELECT * FROM reels WHERE original_video_id=? ORDER BY updated_at DESC LIMIT 1",
            (video_id,),
        ).fetchone()

    def by_video_id(self, video_id):
        return self.cx.execute(
            "SELECT * FROM reels WHERE selected_video_id=?", (video_id,)
        ).fetchone()

    def get_or_create_serial(self, selected):
        row = self.by_video_id(selected["id"])
        if row:
            return int(row["serial"])
        serial = self._next_serial()
        now = utc_now()
        self.cx.execute("""
            INSERT INTO reels(
                serial,selected_video_id,selected_video_title,selected_video_url,
                original_json,selected_json,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)
        """, (
            serial, selected["id"], selected["title"], selected["url"],
            _json({}), _json(selected), now, now
        ))
        self.cx.execute("""
            INSERT INTO reel_selection_history(
                serial,selected_video_id,selected_video_title,selected_video_url,mode,created_at
            ) VALUES(?,?,?,?,?,?)
        """, (serial, selected["id"], selected["title"], selected["url"], "initial", now))
        self.cx.commit()
        return serial

    def set_selected(self, serial, original, selected, search_results=None, mode="automatic"):
        current = self.get(serial)
        if current and current["selected_video_id"] != selected["id"]:
            conflict = self.by_video_id(selected["id"])
            if conflict and int(conflict["serial"]) != int(serial):
                raise ValueError(
                    f"YouTube video {selected['id']} is already assigned to serial {int(conflict['serial']):04d}."
                )
        now = utc_now()
        self.cx.execute("""
            UPDATE reels SET
                selected_video_id=?, selected_video_title=?, selected_video_url=?,
                original_playlist_id=?, original_video_id=?,
                original_json=?, selected_json=?, search_json=?,
                error=NULL, updated_at=?
            WHERE serial=?
        """, (
            selected["id"], selected["title"], selected["url"],
            original.get("playlist_id"), original.get("id"),
            _json(original), _json(selected), _json(search_results or []),
            now, int(serial)
        ))
        self.cx.execute("""
            INSERT INTO reel_selection_history(
                serial,selected_video_id,selected_video_title,selected_video_url,mode,created_at
            ) VALUES(?,?,?,?,?,?)
        """, (serial, selected["id"], selected["title"], selected["url"], mode, now))
        self.cx.commit()

    def selected_exists(self, video_id, exclude_serial=None):
        if exclude_serial is None:
            row = self.cx.execute(
                "SELECT serial FROM reels WHERE selected_video_id=? AND status='FINISHED'",
                (video_id,)
            ).fetchone()
        else:
            row = self.cx.execute(
                "SELECT serial FROM reels WHERE selected_video_id=? AND status='FINISHED' AND serial<>?",
                (video_id, int(exclude_serial))
            ).fetchone()
        return int(row["serial"]) if row else None

    def set_status(self, serial, status, error=None):
        status = str(status).upper()
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid reel status: {status}")
        now = utc_now()
        if status == "PROCESSING":
            self.cx.execute("""
                UPDATE reels SET status=?,error=?,attempt_count=attempt_count+1,
                    updated_at=? WHERE serial=?
            """, (status, error, now, int(serial)))
        else:
            self.cx.execute("""
                UPDATE reels SET status=?,error=?,updated_at=? WHERE serial=?
            """, (status, error, now, int(serial)))
        self.cx.commit()

    def finish(self, serial, metadata, final_path, final_json_path):
        metadata = metadata or {}
        source_sha = metadata.get("downloaded_source", {}).get("sha256")
        final_sha = metadata.get("final_reel", {}).get("sha256")
        now = utc_now()
        self.cx.execute("""
            UPDATE reels SET
                status='FINISHED', error=NULL, metadata_json=?,
                final_path=?, final_json_path=?,
                source_sha256=?, final_sha256=?,
                updated_at=?, completed_at=?
            WHERE serial=?
        """, (
            _json(metadata), str(final_path), str(final_json_path),
            source_sha, final_sha, now, now, int(serial)
        ))
        self.cx.commit()

    def record_skip(self, original, reason, serial=None):
        now = utc_now()
        self.cx.execute("""
            INSERT INTO reel_skips(serial,original_video_id,original_json,reason,created_at)
            VALUES(?,?,?,?,?)
        """, (
            serial, original.get("id"), _json(original), reason, now
        ))
        if serial is not None and self.get(serial):
            self.cx.execute("""
                UPDATE reels SET status='SKIPPED',error=?,updated_at=? WHERE serial=?
            """, (reason, now, int(serial)))
        self.cx.commit()

    def event(self, serial, stage, message):
        self.cx.execute("""
            INSERT INTO reel_events(serial,stage,message,created_at)
            VALUES(?,?,?,?)
        """, (serial, stage, message, utc_now()))
        self.cx.commit()

    def reset(self, serial):
        if not self.get(serial):
            raise ValueError(f"Serial {serial} was not found.")
        self.set_status(serial, "PENDING", None)

    def recover_processing(self):
        self.cx.execute("""
            UPDATE reels SET status='ERROR',
                error=COALESCE(error,'Recovered stale PROCESSING state'),
                updated_at=?
            WHERE status='PROCESSING'
        """, (utc_now(),))
        self.cx.commit()
