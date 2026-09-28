from __future__ import annotations
import sqlite3, json
from pathlib import Path
from .utils import now_iso

SCHEMA='''
CREATE TABLE IF NOT EXISTS jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 song_basename TEXT NOT NULL UNIQUE,
 mp3_sha256 TEXT NOT NULL,
 lrc_sha256 TEXT NOT NULL,
 json_sha256 TEXT NOT NULL,
 processing_identity TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 stage TEXT,
 quality_status TEXT,
 hook_selection_mode TEXT NOT NULL DEFAULT 'automatic',
 manual_hook_start_ms INTEGER,
 manual_hook_end_ms INTEGER,
 error_code TEXT,
 error_message TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
 completed_at TEXT
);

CREATE TABLE IF NOT EXISTS video_matches (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 job_id INTEGER NOT NULL,
 youtube_video_id TEXT NOT NULL,
 query_start_ms INTEGER NOT NULL,
 query_end_ms INTEGER NOT NULL,
 match_start_ms INTEGER,
 match_end_ms INTEGER,
 confidence REAL,
 coarse_similarity REAL,
 fine_similarity REAL,
 anchor_residual_ms REAL,
 accepted INTEGER NOT NULL DEFAULT 0,
 result_json TEXT,
 FOREIGN KEY(job_id) REFERENCES jobs(id)
);
CREATE TABLE IF NOT EXISTS artifacts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 job_id INTEGER NOT NULL,
 artifact_type TEXT NOT NULL,
 path TEXT NOT NULL,
 sha256 TEXT,
 size_bytes INTEGER,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(job_id) REFERENCES jobs(id)
);
'''

class DB:
    def __init__(self,path:Path): self.path=path; self.path.parent.mkdir(parents=True,exist_ok=True); self.conn=sqlite3.connect(str(path)); self.conn.row_factory=sqlite3.Row; self.conn.executescript(SCHEMA); self.conn.commit()
    def upsert_job(self,**kw):
        name=kw['song_basename']; row=self.conn.execute('SELECT id FROM jobs WHERE song_basename=?',(name,)).fetchone()
        if row:
            sets=[]; vals=[]
            for k,v in kw.items():
                if k=='song_basename': continue
                sets.append(f'{k}=?'); vals.append(v)
            sets.append('updated_at=?'); vals.append(now_iso()); vals.append(name)
            self.conn.execute(f"UPDATE jobs SET {','.join(sets)} WHERE song_basename=?",vals)
        else:
            cols=list(kw.keys()); vals=[kw[c] for c in cols]; self.conn.execute(f"INSERT INTO jobs ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",vals)
        self.conn.commit(); return self.conn.execute('SELECT * FROM jobs WHERE song_basename=?',(name,)).fetchone()
    def get_job(self,name): return self.conn.execute('SELECT * FROM jobs WHERE song_basename=?',(name,)).fetchone()
    def pending_jobs(self): return self.conn.execute("SELECT * FROM jobs WHERE status!='finalized' ORDER BY id").fetchall()
    def set_stage(self,name,stage,status=None,error_code=None,error_message=None):
        sets=['stage=?','updated_at=?']; vals=[stage,now_iso()]
        if status: sets.append('status=?'); vals.append(status)
        if error_code is not None: sets.append('error_code=?'); vals.append(error_code)
        if error_message is not None: sets.append('error_message=?'); vals.append(error_message)
        if status=='finalized': sets.append('completed_at=?'); vals.append(now_iso())
        vals.append(name); self.conn.execute(f"UPDATE jobs SET {','.join(sets)} WHERE song_basename=?",vals); self.conn.commit()
    def set_hook_mode(self,name,mode,start=None,end=None):
        self.conn.execute('UPDATE jobs SET hook_selection_mode=?,manual_hook_start_ms=?,manual_hook_end_ms=?,updated_at=? WHERE song_basename=?',(mode,start,end,now_iso(),name)); self.conn.commit()
    def add_match(self,job_id,video_id,result):
        self.conn.execute('INSERT INTO video_matches(job_id,youtube_video_id,query_start_ms,query_end_ms,match_start_ms,match_end_ms,confidence,coarse_similarity,fine_similarity,anchor_residual_ms,accepted,result_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
            job_id,video_id,result.get('query_start_ms',0),result.get('query_end_ms',0),result.get('video_match_start_ms'),result.get('video_match_end_ms'),result.get('confidence'),result.get('coarse_similarity'),result.get('fine_similarity'),result.get('anchor_consistency_ms'),int(result.get('accepted',False)),json.dumps(result,ensure_ascii=False)))
        self.conn.commit()
    def add_artifact(self,job_id,artifact_type,path,sha256=None,size_bytes=None):
        self.conn.execute('INSERT INTO artifacts(job_id,artifact_type,path,sha256,size_bytes) VALUES(?,?,?,?,?)',(job_id,artifact_type,path,sha256,size_bytes)); self.conn.commit()
    def close(self): self.conn.close()
