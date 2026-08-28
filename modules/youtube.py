import json,math,re,subprocess,sys,unicodedata
from pathlib import Path
from rapidfuzz.fuzz import ratio,token_set_ratio,WRatio
WATCH_RE=re.compile(r'https?://(?:www\.)?youtube\.com/watch\?v=([\w-]+)'); SHORT_RE=re.compile(r'https?://youtu\.be/([\w-]+)')
def _cookies():
 p=Path.home()/"cookies.txt"; return ["--cookies",str(p)] if p.is_file() else []
def run(args,check=True):
    # Invoke yt-dlp through the active Python interpreter so the project
    # uses the virtual-environment installation instead of requiring a
    # separate yt-dlp.exe on PATH.
    cmd=[sys.executable,"-m","yt_dlp","--ignore-config",*_cookies(),*args]
    try:
        p=subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        raise RuntimeError(f"Could not start yt-dlp via Python: {e}") from e
    if check and p.returncode:
        output=p.stdout.strip()
        raise RuntimeError(
            f"yt-dlp failed (exit code {p.returncode}).\\n"
            f"{output[-12000:] if output else 'yt-dlp produced no output.'}"
        )
    return p.returncode,p.stdout

def json_output(args,context):
    rc,out=run(args,check=False)
    if rc != 0:
        raise RuntimeError(
            f"{context}: yt-dlp failed (exit code {rc}).\\n"
            f"{out.strip()[-12000:] if out.strip() else 'No output was returned.'}"
        )
    if not out.strip():
        raise RuntimeError(
            f"{context}: yt-dlp returned no output. "
            "Check the yt-dlp error above, playlist URL, network access, "
            "cookies, and YouTube availability."
        )
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"{context}: yt-dlp returned non-JSON output.\\n"
            f"{out.strip()[-12000:]}"
        ) from e

def clean_url(u):
 s=str(u or "").strip();m=WATCH_RE.search(s)
 if m:return f"https://www.youtube.com/watch?v={m.group(1)}"
 m=SHORT_RE.search(s);return f"https://youtu.be/{m.group(1)}" if m else s
def playlist(url):
 d=json_output(
  ["--flat-playlist","--dump-single-json","--skip-download","--quiet","--no-warnings",clean_url(url)],
  "Reading YouTube playlist"
 )
 pid=d.get("id") or "";title=d.get("title") or "";rows=[]
 for e in d.get("entries") or []:
  if e and e.get("id"):rows.append({"id":e["id"],"url":clean_url(e.get("webpage_url") or f"https://www.youtube.com/watch?v={e['id']}"),"title":e.get("title") or ""})
 return pid,title,rows
def info(url):
 return json_output(
  ["--dump-single-json","--skip-download","--quiet","--no-warnings",clean_url(url)],
  "Reading YouTube video metadata"
 )
def search(q,count=10):
 _,o=run(["--default-search","ytsearch","--flat-playlist","--playlist-end",str(max(1,int(count))),"--dump-json","--skip-download","--quiet","--no-warnings",str(q).strip()]);rows=[]
 for line in o.splitlines():
  try:d=json.loads(line)
  except:continue
  if d.get("id"):rows.append({"id":d["id"],"url":clean_url(d.get("webpage_url") or f"https://www.youtube.com/watch?v={d['id']}"),"title":d.get("title") or "","channel":d.get("channel") or d.get("uploader") or "","duration":d.get("duration"),"view_count":d.get("view_count"),"upload_date":d.get("upload_date")})
 return rows
def norm(s):return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',str(s or '').lower()),flags=re.UNICODE).strip()
def core(s):
 s=re.sub(r'\s*[\[(]\s*from\b[^\])]*[\])]',' ',unicodedata.normalize('NFKC',str(s or '')),flags=re.I);return re.sub(r'\s+',' ',re.sub(r'\bfrom\b.*$','',norm(s))).strip()
def tscore(a,b):
 a=core(a);b=norm(b)
 if not a or not b:return 0
 if ''.join(a.split()) in ''.join(b.split()):return 1
 return max(ratio(a,b),token_set_ratio(a,b),WRatio(a,b))/100
def dscore(a,b):
 try:return max(0,1-abs(float(a)-float(b))/max(float(a),float(b),1))
 except:return 0
def penalty(title):
 t=norm(title);p=0;rs=[]
 for pat,amt,r in [(r'\b(?:slowed|reverb|sped\s*up|nightcore)\b',.14,'alternate_speed'),(r'\b(?:remix|remastered|8d|lofi|lo-fi)\b',.12,'alternate_version'),(r'\b(?:cover|karaoke|instrumental)\b',.20,'cover_or_instrumental'),(r'\b(?:bts|behind\s+the\s+scenes|making)\b',.22,'behind_the_scenes'),(r'\b(?:teaser|trailer|promo|shorts?)\b',.24,'promo_or_short'),(r'\b(?:audio|audio\s+song)\b',.12,'audio_only'),(r'\b(?:jukebox|playlist|mix)\b',.22,'collection')]:
  if re.search(pat,t):p+=amt;rs.append(r)
 return min(.5,p),rs
def rank(results,playlist_title,reference=None,cfg=None):
 w=(cfg or {}).get('youtube_search',{});maxv=max([int(r.get('view_count') or 0) for r in results] or [0]);out=[];ref=reference or {}; ref_title=ref.get('title') or playlist_title; ref_d=ref.get('duration'); artists=ref.get('artists') or [];album=ref.get('album') or ref.get('album_title') or ''
 for r in results:
  title=.55*tscore(playlist_title,r['title'])+.45*tscore(ref_title,r['title']) if reference else tscore(playlist_title,r['title']);ch=norm(r.get('channel'));official=1 if any(x in ch for x in ['official','music','aditya','saregama','sony','t-series','lahari','tips','geetha','sun']) else 0;word=1 if re.search(r'\bfull\s+video\s+song\b',norm(r['title'])) else .85 if re.search(r'\bvideo\s+song\b',norm(r['title'])) else .55 if re.search(r'\bfull\s+video\b',norm(r['title'])) else 0;version=0 if penalty(r['title'])[0]>.18 else 1;views=int(r.get('view_count') or 0);view=min(1,math.log10(views+1)/math.log10(maxv+1)) if maxv else 0;dur=dscore(ref_d,r.get('duration'));artist_match=1 if artists and any(norm(a) and norm(a) in norm(r['title']) for a in artists) else 0;album_match=1 if album and norm(album) in norm(r['title']) else 0;p,rs=penalty(r['title']);score=w.get('title_weight',.38)*title+w.get('artist_weight',.20)*artist_match+w.get('album_movie_weight',.12)*album_match+w.get('official_channel_weight',.08)*official+w.get('version_weight',.08)*version+w.get('duration_weight',.06)*dur+w.get('view_weight',.08)*view+(.04 if word else 0)-p
  out.append({'score':round(score,6),'title_match':round(title,6),'artist_match':artist_match,'album_movie_match':album_match,'official_channel_score':official,'version_score':version,'duration_score':round(dur,6),'view_score':round(view,6),'view_count':views,'video_wording_score':word,'penalty':round(p,6),'penalty_reasons':rs,'result':r})
 out.sort(key=lambda x:x['score'],reverse=True)
 for i,x in enumerate(out,1):x['rank']=i
 return out
def choose(ranked,mode):
 if not ranked:raise RuntimeError("No YouTube search results.")
 if mode=='automatic':return ranked[0]['result'],ranked
 print('\nTop YouTube results:')
 for x in ranked[:5]:
  r=x['result'];print(f"[{x['rank']}] score={x['score']:.3f} views={r.get('view_count') or 0} | {r['title']} | {r.get('channel','')} | {r['url']}")
 while 1:
  s=input('Choose 1-5, or q to cancel: ').strip().lower()
  if s=='q':raise KeyboardInterrupt
  if s.isdigit() and 1<=int(s)<=min(5,len(ranked)):return ranked[int(s)-1]['result'],ranked
def select_manual_lrc(metadata,title):
 subs=metadata.get('subtitles') or {};original=(metadata.get('language') or metadata.get('original_language') or '').lower();
 if not subs:return None
 script=None
 for ch in title:
  o=ord(ch)
  if 0x0C00<=o<=0x0C7F:script='te';break
  if 0x0B80<=o<=0x0BFF:script='ta';break
  if 0x0C80<=o<=0x0CFF:script='kn';break
  if 0x0900<=o<=0x097F:script='hi';break
 def ranklang(lang):
  l=lang.lower();score=0
  if original and (l==original or l.startswith(original)):score+=100
  if script and (l==script or l.startswith(script)):score+=80
  if l in {'en','en-us','en-gb'}:score+=50
  return score
 lang=max(subs,key=ranklang);prio='original_language' if ranklang(lang)>=100 else 'english' if ranklang(lang)>=50 else 'other';return {'language':lang,'priority':prio}
def download_video_and_lrc(url,temp,title):
 temp=Path(temp);temp.mkdir(parents=True,exist_ok=True);meta=info(url);sel=select_manual_lrc(meta,title);video_template=str(temp/'youtube_source.%(ext)s');download_args=['-f','bv*+ba/b','--merge-output-format','mp4','-o',video_template,'--no-playlist']
 if sel: download_args += ['--write-subs','--sub-langs',sel['language'],'--sub-format','vtt','--convert-subs','lrc','-o',str(temp/'youtube_source.%(ext)s')]
 run(download_args+[clean_url(url)]);videos=[p for p in temp.glob('youtube_source.*') if p.suffix.lower()=='.mp4'];
 if not videos:raise RuntimeError('yt-dlp did not produce merged YouTube MP4')
 video=max(videos,key=lambda p:p.stat().st_size);lrc=None;lmeta=None
 if sel:
  lrc=next(iter(sorted(temp.glob('youtube_source*.lrc'))),None)
  if lrc:lmeta={'source':'youtube','language':sel['language'],'selection_priority':sel['priority'],'automatic':False}
 return video,meta,lrc,lmeta
