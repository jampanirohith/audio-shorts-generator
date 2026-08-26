import json, re, subprocess
from pathlib import Path


def _cookie_args():
    """Use only an explicit cookies.txt in the user's home directory.
    No browser-cookie extraction or browser integration is used.
    """
    p = Path.home() / 'cookies.txt'
    return ['--cookies', str(p)] if p.is_file() else []

def _run(args, merge=False, show_output=True):
    """Run yt-dlp visibly in the terminal while still capturing its output."""
    cmd=['yt-dlp','--ignore-config',*_cookie_args(),*args]
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                       encoding='utf-8',errors='replace',bufsize=1)
    lines=[]
    if p.stdout:
        for line in p.stdout:
            line=line.rstrip("\r\n")
            lines.append(line)
            if show_output and line:
                print(line, flush=True)
    code=p.wait()
    out='\n'.join(lines)
    return (code,out) if merge else (code,out,'')


def playlist(url):
    """Read playlist directly with yt-dlp. Uses only ~/cookies.txt when present; no browser access."""
    code,out,err=_run(['--flat-playlist','--dump-single-json','--quiet','--no-warnings',url])
    if code: raise RuntimeError(err or out)
    d=json.loads(out)
    rows=[]
    for serial,e in enumerate(d.get('entries') or [],1):
        if not e: continue
        vid=e.get('id')
        rows.append({'serial':serial,'title':e.get('title') or '',
                     'id':vid,'url':e.get('webpage_url') or f'https://www.youtube.com/watch?v={vid}'})
    return rows

def search(query,n=10):
    code,out,err=_run([f'ytsearch{n}:{query}','--flat-playlist','--dump-json','--skip-download','--quiet','--no-warnings'])
    if code: raise RuntimeError(err or out)
    rows=[]
    for line in out.splitlines():
        try:
            d=json.loads(line); vid=d.get('id')
            if vid: rows.append({'id':vid,'url':d.get('webpage_url') or f'https://www.youtube.com/watch?v={vid}',
                'title':d.get('title') or '','channel':d.get('channel') or d.get('uploader') or '',
                'duration':d.get('duration')})
        except Exception: pass
    return rows

def _norm(s):
    return re.sub(r'[^a-z0-9\u0c00-\u0c7f]+',' ',(s or '').lower()).strip()

def _title_score(query,title):
    from rapidfuzz.fuzz import token_set_ratio, ratio
    q,t=_norm(query),_norm(title)
    return max(token_set_ratio(q,t),ratio(q,t))/100.0 if q and t else 0.0

def _video_score(title,keywords):
    t=_norm(title)
    # Strong explicit priority: video-song wording beats channel reputation.
    if re.search(r'\bfull\s+video\s+song\b',t): base=1.0
    elif re.search(r'\bvideo\s+song\b',t): base=.95
    elif re.search(r'\bfull\s+video\b',t): base=.78
    elif re.search(r'\bofficial\s+video\b|\bvideo\b',t): base=.60
    elif 'lyric' in t: base=.12
    else: base=0.0
    for k in keywords:
        if _norm(k) in t: base=max(base,.90 if 'video song' in _norm(k) else .70)
    return base

def auto_choose(results,source_title,cfg):
    a=cfg.get('automation',{})
    keywords=a.get('auto_youtube_keywords',['full video song','video song','full video'])
    rows=[]
    for r in results:
        ts=_title_score(source_title,r['title'])
        vs=_video_score(r['title'],keywords)
        # 70% title match, 30% explicit video wording; no channel score at all.
        score=.70*ts+.30*vs
        if vs>=.95: score+=.18
        rows.append((score,r,ts,vs))
    rows.sort(key=lambda x:x[0],reverse=True)
    return rows

def choose(results,source_title,cfg):
    if cfg.get('automation',{}).get('auto_youtube_selection',True):
        ranked=auto_choose(results,source_title,cfg)
        if not ranked: raise RuntimeError('No YouTube candidates found.')
        # Automatic mode is intentionally quiet: do not print the candidate
        # YouTube titles before processing. The selected video is retained in
        # the database metadata for audit/retry purposes.
        selected=ranked[0][1]
        print('\\nAUTO YouTube selection (channels intentionally ignored):')
        print(f'  Selected: {selected["title"]}')
        print(f'  URL:      {selected["url"]}')
        return selected
    print('\nTop YouTube results:')
    for i,r in enumerate(results,1): print(f'[{i}] {r["title"]} | {r["channel"]} | {r["url"]}')
    while True:
        x=input(f'Choose YouTube result [1-{len(results)}], s=skip, q=quit: ').strip().lower()
        if x == 's': return 'skip'
        if x == 'q': return 'quit'
        if x.isdigit() and 1<=int(x)<=len(results): return results[int(x)-1]

def info(url):
    code,out,err=_run(['--dump-single-json','--skip-download','--quiet','--no-warnings',url])
    if code: raise RuntimeError(err or out)
    return json.loads(out)

def download(url,temp):
    temp=Path(temp); temp.mkdir(parents=True,exist_ok=True)
    out=str(temp/'source [%(id)s].%(ext)s')
    code,outlog=_run(['-f','bv*+ba/b','--merge-output-format','mp4','--no-playlist','-o',out,url],True)
    if code: raise RuntimeError(outlog[-8000:])
    files=list(temp.glob('source [*].mp4'))+list(temp.glob('*.mp4'))
    if not files: raise RuntimeError('yt-dlp finished but no MP4 was produced.')
    return max(files,key=lambda p:p.stat().st_size)

def download_original_subtitles(url,temp,info_json):
    """Download only creator-provided subtitles; never auto-generated/translated tracks."""
    subs=info_json.get('subtitles') or {}
    if not subs: return None
    # Prefer common original-language labels, then first creator-provided track.
    preferred=['te','tel','en','hi','ta','ml','kn']
    lang=next((x for x in preferred if x in subs),next(iter(subs),None))
    if not lang: return None
    temp=Path(temp); before=set(temp.glob('*.vtt'))
    code,out=_run(['--skip-download','--write-subs','--sub-langs',lang,'--sub-format','vtt','-o',str(temp/'lyrics.%(ext)s'),url],True)
    if code: return None
    after=[p for p in temp.glob('*.vtt') if p not in before] or list(temp.glob('*.vtt'))
    return max(after,key=lambda p:p.stat().st_mtime) if after else None

def metadata_clues(d):
    return {'title':d.get('title',''),'channel':d.get('channel') or d.get('uploader') or '',
            'duration':d.get('duration'),'upload_date':d.get('upload_date'),'description':d.get('description') or ''}
