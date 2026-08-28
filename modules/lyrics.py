import re
import subprocess
from pathlib import Path
def parse_lrc(src):
 p=Path(str(src));text=p.read_text(encoding='utf-8-sig',errors='replace') if p.is_file() else str(src or '');out=[]
 for line in text.splitlines():
  tags=re.findall(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]',line);txt=re.sub(r'\[[^\]]+\]','',line).strip()
  for mm,ss,fr in tags:
   t=int(mm)*60+int(ss)+(int(fr or 0)/(1000 if fr and len(fr)==3 else 100));
   if txt:out.append({'time':round(t,3),'text':txt})
 return sorted(out,key=lambda x:x['time'])
def _librelyrics_executable():
    """Return the LibreLyrics CLI from the active Python environment."""
    import shutil, sys
    exe = shutil.which("librelyrics")
    if exe:
        return exe
    scripts = Path(sys.executable).resolve().parent
    for name in ("librelyrics.exe", "librelyrics"):
        candidate = scripts / name
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("LibreLyrics CLI executable was not found in the active virtual environment.")


def _configure_sp_dc(cfg):
    """Synchronize project sp_dc into LibreLyrics' persistent plugin config.

    LibreLyrics/core and the Spotify plugin have appeared with both
    `plugins.spotify.sp_dc` and `plugins.Spotify.sp_dc` namespaces.  The
    installed CLI is the authoritative configuration interface, so configure
    both keys through the real `librelyrics` executable (never `python -m`).
    """
    value = str(cfg.get("librelyrics", {}).get("sp_dc", "") or "").strip()
    if not value or value.upper().startswith("YOUR_"):
        raise RuntimeError("LibreLyrics Spotify sp_dc is missing in config.json (librelyrics.sp_dc).")

    exe = _librelyrics_executable()
    errors = []
    for key in ("plugins.Spotify.sp_dc", "plugins.spotify.sp_dc"):
        try:
            cp = subprocess.run(
                [exe, "config", "set", key, value],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as e:
            errors.append(f"{key}: {e}")
            continue
        if cp.returncode != 0:
            detail = (cp.stderr or cp.stdout or "command failed").strip()
            errors.append(f"{key}: {detail}")
    if errors:
        raise RuntimeError("Could not configure LibreLyrics Spotify sp_dc: " + " | ".join(errors))


def _validate_sp_dc_config(cfg):
    # Keep the project-level credential as the single source of truth, then
    # synchronize it into LibreLyrics' own persistent configuration.
    _configure_sp_dc(cfg)

def fetch_librelyrics(url,out,cfg):
 if not cfg.get('librelyrics',{}).get('enabled',True):return None
 try:
  _validate_sp_dc_config(cfg)
  from librelyrics import LibreLyrics
  # LibreLyrics' current library API is fetch(url); lyric-type selection is
  # controlled by LibreLyrics configuration (synced_lyrics), not a
  # lyrics_type keyword argument. Passing that keyword breaks on current
  # releases with: unexpected keyword argument 'lyrics_type'.
  response=LibreLyrics().fetch(url)
  text=response.to_lrc(include_metadata=True,enhanced=bool(cfg.get('librelyrics',{}).get('enhanced_lrc',False)))
  if not text.strip():return None
  p=Path(out);p.write_text(text,encoding='utf-8');return p
 except Exception as e:
  # Lyrics are optional in this pipeline. LibreLyrics may legitimately have
  # no entry for instrumentals, teasers, themes, regional releases, etc.
  # Treat an explicit 'no lyrics available' response as a recoverable miss;
  # the hook detector will continue with YouTube LRC or audio-only analysis.
  msg=str(e)
  low=msg.lower()
  no_lyrics_markers=(
   'no lyrics available',
   'lyrics not found',
   'no synced lyrics',
   'no lyrics found',
   'lyrics unavailable',
   'could not find lyrics',
  )
  if any(marker in low for marker in no_lyrics_markers):
   try: Path(out).unlink(missing_ok=True)
   except Exception: pass
   return None
  raise RuntimeError(f'LibreLyrics failed: {e}') from e
def embed_lrc_mp3(audio,lrc):
 from mutagen.mp3 import MP3
 from mutagen.id3 import ID3,USLT,SYLT
 a=MP3(str(audio),ID3=ID3)
 try:a.add_tags()
 except:pass
 a.tags.delall('USLT');a.tags.delall('SYLT');lines=parse_lrc(lrc);sylt=[(x['text'],int(x['time']*1000)) for x in lines]
 if sylt:a.tags.add(SYLT(encoding=3,lang='eng',format=2,desc='LibreLyrics',text=sylt))
 a.tags.add(USLT(encoding=3,lang='eng',desc='LibreLyrics LRC',text=lrc));a.save()
def lines_in_range(lines,s,e):return [x for x in lines if s<=x['time']<e]
