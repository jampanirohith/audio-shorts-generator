import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def parse_lrc(src):
    p=Path(str(src)); text=p.read_text(encoding='utf-8-sig',errors='replace') if p.is_file() else str(src or '')
    out=[]
    for line in text.splitlines():
        tags=re.findall(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]',line)
        txt=re.sub(r'\[[^\]]+\]','',line).strip()
        for mm,ss,fr in tags:
            t=int(mm)*60+int(ss)+(int(fr or 0)/(1000 if fr and len(fr)==3 else 100))
            if txt: out.append({'time':round(t,3),'text':txt})
    return sorted(out,key=lambda x:x['time'])


def _exe():
    e=shutil.which('librelyrics')
    if e:return e
    p=Path(sys.executable).resolve().parent
    for n in ('librelyrics.exe','librelyrics'):
        q=p/n
        if q.is_file():return str(q)
    raise RuntimeError('LibreLyrics CLI executable was not found in the active virtual environment.')


def _configure_sp_dc():
    value=os.getenv('SPOTIFY_SP_DC','').strip()
    if not value: raise RuntimeError('SPOTIFY_SP_DC is missing from .env')
    exe=_exe(); successes=[]; errors=[]
    # LibreLyrics releases have differed in key casing. Try the actual CLI command
    # against both known spellings; the value itself never reaches normal output.
    for key in ('plugins.spotify.sp_dc','plugins.Spotify.sp_dc'):
        p=subprocess.run([exe,'config','set',key,value],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
        if p.returncode==0: successes.append(key)
        else: errors.append(f'{key}: {(p.stderr or p.stdout or "command failed").strip()}')
    if not successes:
        raise RuntimeError('Could not configure LibreLyrics Spotify sp_dc. ' + ' | '.join(errors))


def fetch_librelyrics(url,out,cfg):
    if not cfg.get('librelyrics',{}).get('enabled',True): return None
    try:
        _configure_sp_dc()
        from librelyrics import LibreLyrics
        response=LibreLyrics().fetch(url)
        text=response.to_lrc(include_metadata=True,enhanced=bool(cfg.get('librelyrics',{}).get('enhanced_lrc',False)))
        if not text.strip(): return None
        p=Path(out);p.write_text(text,encoding='utf-8');return p
    except Exception as e:
        low=str(e).lower()
        if any(x in low for x in ('no lyrics available','lyrics not found','no synced lyrics','no lyrics found','lyrics unavailable','could not find lyrics')):
            Path(out).unlink(missing_ok=True); return None
        raise RuntimeError(f'LibreLyrics failed: {e}') from e


def lines_in_range(lines,s,e):
    return [x for x in lines if s <= x['time'] < e]


def hook_relative_lines(lrc, start, end):
    if not lrc: return []
    lines=parse_lrc(lrc) if isinstance(lrc,(str,Path)) else list(lrc)
    out=[]
    for x in lines:
        if start <= x['time'] < end:
            out.append({'time':round(x['time']-start,3),'text':x['text']})
    return out


def embed_lrc_mp3(audio,lrc):
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3,USLT,SYLT
    a=MP3(str(audio),ID3=ID3)
    try:a.add_tags()
    except Exception:pass
    a.tags.delall('USLT');a.tags.delall('SYLT')
    lines=parse_lrc(lrc);sylt=[(x['text'],int(x['time']*1000)) for x in lines]
    if sylt:a.tags.add(SYLT(encoding=3,lang='eng',format=2,desc='Spotify LRC',text=sylt))
    a.tags.add(USLT(encoding=3,lang='eng',desc='Spotify LRC',text=Path(lrc).read_text(encoding='utf-8-sig',errors='replace')));a.save()
