import json, math, re, subprocess, sys, unicodedata
from pathlib import Path
from rapidfuzz.fuzz import ratio, token_set_ratio, WRatio

WATCH_RE=re.compile(r'https?://(?:www\.)?youtube\.com/watch\?v=([\w-]+)')
SHORT_RE=re.compile(r'https?://youtu\.be/([\w-]+)')


def _cookies():
    p=Path(__file__).resolve().parent.parent/'cookies.txt'
    return ['--cookies',str(p)] if p.is_file() else []


def run(args,check=True):
    cmd=[sys.executable,'-m','yt_dlp']+list(args)+_cookies()
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    if check and p.returncode: raise RuntimeError(f'yt-dlp failed (exit code {p.returncode}).\n{p.stdout[-12000:]}')
    return p.returncode,p.stdout or ''


def clean_url(u):
    s=str(u or '').strip();m=WATCH_RE.search(s)
    if m:return f'https://www.youtube.com/watch?v={m.group(1)}'
    m=SHORT_RE.search(s)
    return f'https://youtu.be/{m.group(1)}' if m else s


def search(query,count=10):
    _,out=run(['--default-search','ytsearch','--flat-playlist','--playlist-end',str(max(1,int(count))),'--dump-json','--skip-download','--quiet','--no-warnings',str(query).strip()])
    rows=[]
    for line in out.splitlines():
        try:d=json.loads(line)
        except Exception:continue
        if d.get('id'):
            rows.append({'id':d['id'],'url':clean_url(d.get('webpage_url') or f"https://www.youtube.com/watch?v={d['id']}"),'title':d.get('title') or '','channel':d.get('channel') or d.get('uploader') or '','duration':d.get('duration'),'view_count':d.get('view_count'),'upload_date':d.get('upload_date')})
    return rows


def info(url):
    _,out=run(['--dump-single-json','--skip-download','--quiet','--no-warnings',clean_url(url)])
    return json.loads(out)


def norm(s):return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',str(s or '').lower()),flags=re.UNICODE).strip()

def core(s):
    x=unicodedata.normalize('NFKC',str(s or ''))
    x=re.sub(r'\s*[\[(]\s*from\b[^\])]*[\)]',' ',x,flags=re.I)
    x=re.sub(r'\bfrom\b.*$','',norm(x))
    return re.sub(r'\s+',' ',x).strip()

def tscore(a,b):
    a=core(a);b=norm(b)
    if not a or not b:return 0
    if ''.join(a.split()) in ''.join(b.split()):return 1
    return max(ratio(a,b),token_set_ratio(a,b),WRatio(a,b))/100

def dscore(a,b):
    try:return max(0,1-abs(float(a)-float(b))/max(float(a),float(b),1))
    except:return 0

def _penalty(title):
    t=norm(title);p=0;reasons=[]
    for pat,amt,reason in [
        (r'\b(?:slowed|reverb|sped\s*up|nightcore)\b',.10,'alternate_speed'),
        (r'\b(?:remix|remastered|8d|lofi|lo-fi)\b',.08,'alternate_version'),
        (r'\b(?:cover|karaoke|instrumental)\b',.20,'cover_or_instrumental'),
        (r'\b(?:bts|behind\s+the\s+scenes|making)\b',.22,'behind_the_scenes'),
        (r'\b(?:teaser|trailer|promo|shorts?)\b',.20,'promo_or_short'),
        (r'\b(?:audio|audio\s+song)\b',.06,'audio_only'),
        (r'\b(?:jukebox|playlist|mix|compilation)\b',.18,'collection')]:
        if re.search(pat,t):p+=amt;reasons.append(reason)
    return min(.40,p),reasons


def rank(results,title,artist='',album='',duration=None,cfg=None):
    w=(cfg or {}).get('youtube_search',{});maxv=max([int(r.get('view_count') or 0) for r in results] or [0]);out=[]
    artists=' '.join(artist) if isinstance(artist,list) else str(artist or '')
    for r in results:
        tm=tscore(title,r['title']);am=tscore(artists,r['title']) if artists else 0;alm=tscore(album,r['title']) if album else 0
        ch=norm(r.get('channel'));official=1 if any(x in ch for x in ['official','music','saregama','sony','t-series','lahari','tips','geetha','sun','aditya','mango']) else 0
        wording=1 if re.search(r'\bfull\s+video\s+song\b',norm(r['title'])) else .9 if re.search(r'\bvideo\s+song\b',norm(r['title'])) else .55 if re.search(r'\bfull\s+video\b',norm(r['title'])) else 0
        version=0 if _penalty(r['title'])[0]>.20 else 1
        views=int(r.get('view_count') or 0);view=min(1,math.log10(views+1)/math.log10(maxv+1)) if maxv else 0
        ds=dscore(duration,r.get('duration'));pen,reasons=_penalty(r['title'])
        score=w.get('title_weight',.48)*tm+w.get('artist_weight',.16)*am+w.get('album_movie_weight',.10)*alm+w.get('official_channel_weight',.06)*official+w.get('version_weight',.08)*version+w.get('duration_weight',.04)*ds+w.get('view_weight',.08)*view+(.04 if wording else 0)-pen
        out.append({'rank':0,'score':round(score,6),'title_match':round(tm,6),'artist_match':round(am,6),'album_movie_match':round(alm,6),'official_channel_score':official,'version_score':version,'duration_score':round(ds,6),'view_score':round(view,6),'view_count':views,'video_wording_score':wording,'penalty':round(pen,6),'penalty_reasons':reasons,'result':r})
    out.sort(key=lambda x:x['score'],reverse=True)
    for i,x in enumerate(out,1):x['rank']=i
    return out


def choose(ranked,mode='automatic'):
    if not ranked:raise RuntimeError('No YouTube search results.')
    if mode=='automatic':return ranked[0]['result'],ranked
    print('\nYouTube candidates (manual selection):',flush=True)
    for x in ranked[:5]:
        r=x['result'];print(f"[{x['rank']}] score={x['score']:.3f} | views={r.get('view_count') or 0} | {r['title']} | {r.get('channel','')} | {r['url']}",flush=True)
    while True:
        a=input('Choose YouTube result 1-5, or q to cancel: ').strip().lower()
        if a=='q':raise KeyboardInterrupt
        if a.isdigit() and 1<=int(a)<=min(5,len(ranked)):return ranked[int(a)-1]['result'],ranked


def download_video(url,temp):
    temp=Path(temp);temp.mkdir(parents=True,exist_ok=True)
    template=str(temp/'youtube_source.%(ext)s')
    rc,out=run(['-f','bv*+ba/b','--merge-output-format','mp4','-o',template,'--no-playlist',clean_url(url)])
    files=[p for p in temp.glob('youtube_source.*') if p.suffix.lower()=='.mp4']
    if not files:raise RuntimeError('yt-dlp completed but no merged YouTube MP4 was produced.\n'+out[-6000:])
    return max(files,key=lambda p:p.stat().st_size)
