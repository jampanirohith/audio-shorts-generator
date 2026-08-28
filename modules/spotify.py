import re,subprocess,sys
from pathlib import Path
from rapidfuzz.fuzz import ratio,token_set_ratio,WRatio

def norm(s):return re.sub(r'[^\w]+',' ',str(s or '').lower(),flags=re.UNICODE).strip()
def dur(a,b):
 try:return max(0,1-abs(float(a)-float(b))/max(float(a),float(b),1))
 except:return 0
def asdict(song):
 try:return dict(song.json)
 except Exception:return vars(song)
def _downloader_settings(cfg, out):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    return {
        "output": str(out/"spotify_source.{output-ext}"),
        "format": cfg.get("spotify_output_format","mp3"),
        "archive": str(out/".spotdl_archive.txt"),
        "save_errors": None,
        "print_errors": True,
        "generate_lrc": False,
        "overwrite": "force",
        "fetch_albums": False,
        "m3u": None,
        "save_file": None,
        "scan_for_songs": False,
        "threads": 1,
        "simple_tui": True,
        "playlist_numbering": False,
        "add_unavailable": False,
    }

def create_client(cfg, out):
    """Create the ONE SpotDL client for the current pipeline job.

    SpotDL 4.5.2 initializes a process-wide SpotifyClient in Spotdl.__init__.
    Therefore this function must be called exactly once per main.py process/job.
    """
    try:
        from spotdl import Spotdl
    except Exception as e:
        raise RuntimeError("spotDL is not installed. Install requirements.txt.") from e
    c=cfg.get("spotify",{})
    client_id=c.get("client_id","")
    client_secret=c.get("client_secret","")
    if not client_id or str(client_id).startswith("YOUR_"):
        raise RuntimeError("Spotify client_id is missing in config.json")
    if not client_secret or str(client_secret).startswith("YOUR_"):
        raise RuntimeError("Spotify client_secret is missing in config.json")
    return Spotdl(
        client_id=client_id,
        client_secret=client_secret,
        use_official_api=bool(c.get("use_official_api",False)),
        cache_path=c.get("cache_path","state/spotdl-cache"),
        downloader_settings=_downloader_settings(cfg,out),
    )

def search(client, query):
    """Search with the already-created SpotDL client."""
    try:
        return [asdict(s) for s in client.search([query])]
    except Exception as e:
        raise RuntimeError(f"spotDL Spotify search failed: {type(e).__name__}: {e}") from e

def rank(results,title,artists='',album='',duration=None,cfg=None):
 w=(cfg or {}).get('spotify_search',{});artist_text=artists if isinstance(artists,str) else ' '.join(artists or []);out=[]
 for r in results:
  rt=r.get('name') or r.get('title') or '';ra=r.get('artists') or [];ra=' '.join(ra) if isinstance(ra,list) else str(ra);al=r.get('album_name') or r.get('album') or '';ts=max(ratio(norm(title),norm(rt)),token_set_ratio(norm(title),norm(rt)),WRatio(norm(title),norm(rt)))/100;ars=1 if artist_text and norm(artist_text) in norm(ra) else ratio(norm(artist_text),norm(ra))/100 if artist_text else 0;als=1 if album and norm(album) in norm(al) else ratio(norm(album),norm(al))/100 if album else 0;ds=dur(duration,r.get('duration'));score=w.get('title_weight',.42)*ts+w.get('artist_weight',.28)*ars+w.get('album_weight',.18)*als+w.get('duration_weight',.12)*ds;out.append({'rank':0,'score':round(score,6),'title_score':round(ts,6),'artist_score':round(ars,6),'album_score':round(als,6),'duration_score':round(ds,6),'result':r})
 out.sort(key=lambda x:x['score'],reverse=True)
 for i,x in enumerate(out,1):x['rank']=i
 return out
def choose(ranked,mode):
 if not ranked:raise RuntimeError('No Spotify search results.')
 if mode=='automatic':return ranked[0]['result'],ranked
 print('\nTop Spotify results:')
 for x in ranked[:5]:
  r=x['result'];print(f"[{x['rank']}] score={x['score']:.3f} | {r.get('name')} | {', '.join(r.get('artists') or [])} | {r.get('album_name') or r.get('album') or ''} | {r.get('url')}")
 while 1:
  s=input('Choose 1-5, or q to cancel: ').strip().lower()
  if s=='q':raise KeyboardInterrupt
  if s.isdigit() and 1<=int(s)<=min(5,len(ranked)):return ranked[int(s)-1]['result'],ranked
def download(client,song,cfg,out):
    """Download with the SAME SpotDL client used for Spotify search."""
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    url=song.get("url")
    if not url:
        raise RuntimeError("Selected Spotify result has no URL")

    # Do not instantiate Spotdl() here. The downloader was initialized once
    # in create_client() with this job's output/archive paths.
    try:
        songs=client.search([url])
        if not songs:
            raise RuntimeError(f"spotDL could not resolve selected Spotify track: {url}")
        result_song,audio_path=client.download(songs[0])
        if audio_path is None:
            errors=getattr(client.downloader,"errors",None) or []
            detail="; ".join(str(x) for x in errors[-5:])
            raise RuntimeError(
                "spotDL failed to download the selected Spotify track"
                + (f": {detail}" if detail else ".")
            )
        audio=Path(audio_path)
        if not audio.is_file():
            raise RuntimeError(f"spotDL reported success but audio file is missing: {audio}")

        artwork=None
        for candidate in out.iterdir():
            if candidate.suffix.lower() in {".jpg",".jpeg",".png",".webp"}:
                artwork=candidate
                break
        if artwork is None and audio.suffix.lower()==".mp3":
            try:
                from mutagen.mp3 import MP3
                mp3=MP3(str(audio))
                covers=mp3.tags.getall("APIC") if mp3.tags else []
                if covers:
                    cover=covers[0]
                    ext=".png" if str(cover.mime).lower()=="image/png" else ".jpg"
                    artwork=out/"spotdl_artwork"+ext
                    artwork.write_bytes(cover.data)
            except Exception:
                artwork=None
        return audio,artwork
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"spotDL download failed: {type(exc).__name__}: {exc}") from exc

def song_key(song):
 a=song.get('artists') or [];a=' '.join(a) if isinstance(a,list) else str(a);return '|'.join([norm(song.get('name') or song.get('title')),norm(a),norm(song.get('album_name') or song.get('album'))])
