from __future__ import annotations
import json
from pathlib import Path
from .scanner import SongPackage
from .utils import Phase3Error

def recursive_get(obj, path, default=None):
    cur=obj
    for p in path.split('.'):
        if not isinstance(cur,dict) or p not in cur: return default
        cur=cur[p]
    return cur

def extract_word_records(data:dict)->list[dict]:
    roots=[]
    for path in ('phase2.alignment.lines','alignment.lines','lyrics.alignment.lines'):
        v=recursive_get(data,path)
        if isinstance(v,list): roots=v; break
    words=[]
    for li,line in enumerate(roots):
        if not isinstance(line,dict): continue
        ws=line.get('words') or []
        for wi,w in enumerate(ws):
            if not isinstance(w,dict): continue
            if 'start_ms' not in w or 'end_ms' not in w: continue
            item=dict(w); item['line_index']=li; item['word_index']=wi; words.append(item)
    return words

def extract_youtube_video_id(data:dict)->str|None:
    y=data.get('youtube_video')
    if isinstance(y,dict):
        for k in ('video_id','selected_video_id','id'):
            if y.get(k) and not isinstance(y.get(k),bool): return str(y[k])
        if isinstance(y.get('selected'),dict) and y['selected'].get('video_id'): return str(y['selected']['video_id'])
        meta=y.get('metadata')
        if isinstance(meta,dict):
            if meta.get('video_id'): return str(meta['video_id'])
            raw=meta.get('raw')
            if isinstance(raw,dict) and raw.get('video_id'): return str(raw['video_id'])
    # Historical Phase 1 structures may have the record nested.
    for key in ('selected_youtube_video_id','youtube_video_id'):
        if data.get(key): return str(data[key])
    return None

def validate_package(pkg:SongPackage, cfg):
    if not pkg.mp3.exists(): raise Phase3Error('INPUT_MP3_MISSING',str(pkg.mp3))
    if not pkg.lrc.exists(): raise Phase3Error('INPUT_LRC_MISSING',str(pkg.lrc))
    if not pkg.json.exists(): raise Phase3Error('INPUT_JSON_MISSING',str(pkg.json))
    try: data=json.loads(pkg.json.read_text(encoding='utf-8'))
    except Exception as e: raise Phase3Error('INPUT_JSON_INVALID',f'{pkg.json}: {e}')
    words=extract_word_records(data)
    if cfg.get('input.require_word_timing',True) and not words: raise Phase3Error('WORD_TIMELINE_MISSING',f'No word timeline in {pkg.json}')
    yt_id=extract_youtube_video_id(data)
    if cfg.get('input.require_youtube_video_id',True) and not yt_id: raise Phase3Error('YOUTUBE_VIDEO_ID_MISSING',f'No selected video ID in {pkg.json}')
    return {'json':data,'words':words,'youtube_video_id':yt_id}
