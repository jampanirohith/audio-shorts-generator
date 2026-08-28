import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()
def jd(v): return json.dumps(v if v is not None else {}, ensure_ascii=False, default=str)

class PlaylistDB:
    """The playlist DB intentionally contains only playlist entries and their status."""
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cx=sqlite3.connect(self.path,timeout=30); self.cx.row_factory=sqlite3.Row
        self.cx.execute("PRAGMA journal_mode=WAL"); self.cx.execute("PRAGMA synchronous=FULL"); self._schema()
    def _schema(self):
        cols={r[1] for r in self.cx.execute("PRAGMA table_info(playlist_entries)").fetchall()}
        if cols and "video_id" not in cols:
            self.cx.execute("ALTER TABLE playlist_entries RENAME TO playlist_entries_legacy"); self.cx.commit()
        self.cx.executescript("""
        CREATE TABLE IF NOT EXISTS playlist_entries(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          playlist_id TEXT NOT NULL,
          video_id TEXT NOT NULL,
          url TEXT NOT NULL,
          title TEXT NOT NULL,
          playlist_order INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'YET_TO_START' CHECK(status IN ('YET_TO_START','FINISHED')),
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          finished_serial INTEGER,
          UNIQUE(playlist_id,video_id)
        );
        CREATE INDEX IF NOT EXISTS idx_playlist_next ON playlist_entries(playlist_id,status,playlist_order);
        """)
        legacy=self.cx.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlist_entries_legacy'").fetchone()
        if legacy:
            oldcols={r[1] for r in self.cx.execute("PRAGMA table_info(playlist_entries_legacy)").fetchall()}
            if "original_video_id" in oldcols:
                rows=self.cx.execute("SELECT * FROM playlist_entries_legacy ORDER BY id").fetchall()
                for i,r in enumerate(rows,1):
                    status="FINISHED" if str(r["processing_status"] or "").upper()=="FINISHED" else "YET_TO_START"
                    self.cx.execute("INSERT OR IGNORE INTO playlist_entries(playlist_id,video_id,url,title,playlist_order,status,first_seen_at,last_seen_at,finished_serial) VALUES(?,?,?,?,?,?,?,?,?)",(r["playlist_id"],r["original_video_id"],r["original_url"],r["original_title"],i,status,r["first_seen_at"],r["last_seen_at"],r["final_serial"]))
            self.cx.execute("DROP TABLE playlist_entries_legacy")
        self.cx.commit()
    def sync(self,pid,url,title,entries):
        """
        Synchronize the configured playlist without ever reordering existing rows.

        Identity is (playlist_id, video_id). Existing rows are updated in place;
        genuinely new video IDs are appended after the current maximum order.
        The incoming snapshot is also de-duplicated by video ID because YouTube
        playlists can contain the same video more than once. Only the first
        occurrence is considered, preserving its first-seen position.
        """
        t=now()

        # Snapshot existing IDs and the current highest persistent order.
        existing={
            r["video_id"]
            for r in self.cx.execute(
                "SELECT video_id FROM playlist_entries WHERE playlist_id=?",
                (pid,)
            ).fetchall()
        }
        max_order=int(
            self.cx.execute(
                "SELECT COALESCE(MAX(playlist_order),0) AS n "
                "FROM playlist_entries WHERE playlist_id=?",
                (pid,)
            ).fetchone()["n"]
        )

        # A playlist snapshot itself can contain duplicate video IDs. Keep only
        # the first occurrence; never attempt a second INSERT for the same ID.
        seen_snapshot=set()

        try:
            self.cx.execute("BEGIN IMMEDIATE")
            for e in entries:
                vid=str(e.get("id") or "").strip()
                if not vid or vid in seen_snapshot:
                    continue
                seen_snapshot.add(vid)

                eurl=e.get("url") or f"https://www.youtube.com/watch?v={vid}"
                etitle=e.get("title") or ""

                if vid in existing:
                    # Existing order/status are deliberately untouched.
                    self.cx.execute(
                        "UPDATE playlist_entries "
                        "SET last_seen_at=?, url=?, title=? "
                        "WHERE playlist_id=? AND video_id=?",
                        (t,eurl,etitle,pid,vid)
                    )
                else:
                    # Append only genuinely new videos to the bottom.
                    max_order += 1
                    self.cx.execute(
                        "INSERT INTO playlist_entries("
                        "playlist_id,video_id,url,title,playlist_order,status,"
                        "first_seen_at,last_seen_at"
                        ") VALUES(?,?,?,?,?,?,?,?)",
                        (pid,vid,eurl,etitle,max_order,"YET_TO_START",t,t)
                    )
                    existing.add(vid)

            self.cx.commit()
        except Exception:
            self.cx.rollback()
            raise
    def first_pending(self,pid): return self.cx.execute("SELECT * FROM playlist_entries WHERE playlist_id=? AND status='YET_TO_START' ORDER BY playlist_order LIMIT 1",(pid,)).fetchone()
    def set_finished(self,pid,vid,serial): self.cx.execute("UPDATE playlist_entries SET status='FINISHED',finished_serial=? WHERE playlist_id=? AND video_id=?",(serial,pid,vid)); self.cx.commit()
    def reset(self,pid,vid): self.cx.execute("UPDATE playlist_entries SET status='YET_TO_START',finished_serial=NULL WHERE playlist_id=? AND video_id=?",(pid,vid)); self.cx.commit()
    def close(self): self.cx.close()
    def __enter__(self): return self
    def __exit__(self,*a): self.close()

class ReelDB:
    """Permanent serial allocator plus completed reel identity."""
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cx=sqlite3.connect(self.path,timeout=30); self.cx.row_factory=sqlite3.Row
        self.cx.execute("PRAGMA journal_mode=WAL"); self.cx.execute("PRAGMA synchronous=FULL"); self._schema()
    def _schema(self):
        self.cx.executescript("""
        CREATE TABLE IF NOT EXISTS serial_state(id INTEGER PRIMARY KEY CHECK(id=1),next_serial INTEGER NOT NULL);
        INSERT OR IGNORE INTO serial_state(id,next_serial) VALUES(1,1);
        CREATE TABLE IF NOT EXISTS reels(
          serial INTEGER PRIMARY KEY,selected_youtube_id TEXT UNIQUE NOT NULL,selected_youtube_url TEXT NOT NULL,selected_youtube_title TEXT NOT NULL,
          playlist_video_id TEXT,status TEXT NOT NULL,metadata_json TEXT,final_mp4 TEXT,final_json TEXT,created_at TEXT NOT NULL,finished_at TEXT
        );
        """); self.cx.commit()
    def allocate_serial(self):
        self.cx.execute("BEGIN IMMEDIATE"); s=int(self.cx.execute("SELECT next_serial FROM serial_state WHERE id=1").fetchone()["next_serial"]); self.cx.execute("UPDATE serial_state SET next_serial=? WHERE id=1",(s+1,)); self.cx.commit(); return s
    def create(self,s,sel,pvid): self.cx.execute("INSERT INTO reels(serial,selected_youtube_id,selected_youtube_url,selected_youtube_title,playlist_video_id,status,created_at) VALUES(?,?,?,?,?,?,?)",(s,sel["id"],sel["url"],sel["title"],pvid,"PROCESSING",now())); self.cx.commit()
    def finish(self,s,meta,mp4,j): self.cx.execute("UPDATE reels SET status='FINISHED',metadata_json=?,final_mp4=?,final_json=?,finished_at=? WHERE serial=?",(jd(meta),str(mp4),str(j),now(),s)); self.cx.commit()
    def delete_job(self,s): self.cx.execute("DELETE FROM reels WHERE serial=?",(s,)); self.cx.commit()
    def duplicate_youtube(self,vid): return self.cx.execute("SELECT serial FROM reels WHERE selected_youtube_id=? AND status='FINISHED'",(vid,)).fetchone()
    def close(self): self.cx.close()
    def __enter__(self): return self
    def __exit__(self,*a): self.close()

class SongsDB:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cx=sqlite3.connect(self.path,timeout=30); self.cx.row_factory=sqlite3.Row
        self.cx.execute("PRAGMA journal_mode=WAL"); self.cx.execute("PRAGMA synchronous=FULL"); self._schema()
    def _schema(self):
        self.cx.executescript("""
        CREATE TABLE IF NOT EXISTS songs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,serial INTEGER UNIQUE NOT NULL,song_key TEXT UNIQUE NOT NULL,title TEXT,artists TEXT,album TEXT,
          spotify_url TEXT,spotify_track_id TEXT,youtube_video_id TEXT,youtube_url TEXT,spotify_source_file TEXT,spotdl_source_url TEXT,canonical_file TEXT,youtube_title TEXT,artwork_file TEXT,
          lrc_file TEXT,lrc_source TEXT,lrc_language TEXT,lrc_selection_priority TEXT,sync_json TEXT,hook_json TEXT,metadata_json TEXT,created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_song_youtube ON songs(youtube_video_id);
        CREATE INDEX IF NOT EXISTS idx_song_key ON songs(song_key);
        """); self.cx.commit()
    def find_duplicate(self,vid,key): return self.cx.execute("SELECT * FROM songs WHERE youtube_video_id=? OR song_key=? LIMIT 1",(vid,key)).fetchone()
    def delete_serial(self,serial): self.cx.execute("DELETE FROM songs WHERE serial=?",(serial,)); self.cx.commit()
    def insert(self,d):
        cols=['serial','song_key','title','artists','album','spotify_url','spotify_track_id','youtube_video_id','youtube_url','spotify_source_file','spotdl_source_url','canonical_file','youtube_title','artwork_file','lrc_file','lrc_source','lrc_language','lrc_selection_priority','sync_json','hook_json','metadata_json']
        self.cx.execute(f"INSERT INTO songs({','.join(cols)},created_at) VALUES({','.join('?' for _ in cols)},?)",tuple(d.get(k) for k in cols)+(now(),)); self.cx.commit()
    def close(self): self.cx.close()
    def __enter__(self): return self
    def __exit__(self,*a): self.close()
