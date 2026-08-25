import os, re, subprocess, json, hashlib
from pathlib import Path


def run(args, merge_stderr=False):
    p = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    return (p.returncode, p.stdout) if merge_stderr else (p.returncode, p.stdout, p.stderr)


def _api_playlist(url, api_key):
    m = re.search(r'[?&]list=([^&]+)', url)
    if not m:
        return None
    pid = m.group(1)
    token = ''
    items = []
    while True:
        u = f'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet,contentDetails&maxResults=50&playlistId={pid}&key={api_key}'
        if token:
            u += '&pageToken=' + token
        import requests
        r = requests.get(u, timeout=30)
        r.raise_for_status()
        d = r.json()
        for it in d.get('items', []):
            sn = it.get('snippet', {})
            cd = it.get('contentDetails', {})
            vid = cd.get('videoId')
            if not vid:
                continue
            items.append({
                'title': sn.get('title', ''),
                'url': f'https://www.youtube.com/watch?v={vid}',
                'id': vid,
                'playlist_index': (sn.get('position', 0) or 0) + 1,
                # For playlistItems, snippet.publishedAt is the time the item was added to the playlist.
                'playlist_added': sn.get('publishedAt'),
            })
        token = d.get('nextPageToken')
        if not token:
            break
    items.sort(key=lambda x: (x.get('playlist_added') is None, x.get('playlist_added') or '', x.get('playlist_index') or 0))
    return items


def playlist(url):
    api_key = (os.getenv('YOUTUBE_API_KEY') or '').strip()
    if api_key and not api_key.startswith('YOUR_'):
        try:
            out = _api_playlist(url, api_key)
            if out:
                print('Playlist ordering: YouTube playlist-added timestamp (oldest -> newest).')
                return out
        except Exception as e:
            print(f'YouTube Data API unavailable; falling back to playlist order: {e}')
    else:
        print('YOUTUBE_API_KEY is not configured; using playlist position order as fallback.')
    code, out, err = run(['yt-dlp', '--flat-playlist', '--dump-single-json', '--quiet', '--no-warnings', url])
    if code:
        raise RuntimeError(err or out)
    try:
        d = json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'Playlist JSON parse failed: {e}\n{out[:2000]}')
    entries = []
    for i, e in enumerate(d.get('entries') or [], 1):
        if not e:
            continue
        vid = e.get('id')
        u = e.get('webpage_url') or (f'https://www.youtube.com/watch?v={vid}' if vid else '')
        entries.append({
            'title': e.get('title') or '',
            'url': u,
            'id': vid,
            'playlist_index': e.get('playlist_index') or i,
            'playlist_added': e.get('playlist_added'),
        })
    entries.sort(key=lambda x: (x.get('playlist_added') is None, x.get('playlist_added') or '', x.get('playlist_index') or 0))
    return entries


def search(query, n=5):
    code, out, err = run(['yt-dlp', f'ytsearch{n}:{query}', '--flat-playlist', '--dump-json', '--skip-download', '--quiet', '--no-warnings'])
    if code:
        raise RuntimeError(err or out)
    res = []
    for line in out.splitlines():
        try:
            d = json.loads(line)
            vid = d.get('id')
            if not vid:
                continue
            res.append({
                'id': vid,
                'url': d.get('webpage_url') or f'https://www.youtube.com/watch?v={vid}',
                'title': d.get('title', ''),
                'channel': d.get('channel') or d.get('uploader', ''),
                'duration': d.get('duration'),
            })
        except Exception:
            pass
    return res


def _yt_norm(s):
    return re.sub(r'[^a-z0-9\\u0C00-\\u0C7F]+', ' ', (s or '').lower()).strip()


def _channel_match(channel, official):
    c=_yt_norm(channel)
    compact=re.sub(r'[^a-z0-9]','',c)
    scores=[]
    for x in official:
        o=_yt_norm(x); oc=re.sub(r'[^a-z0-9]','',o)
        if not oc: continue
        if c == o or compact == oc:
            scores.append(1.0)
        elif oc in compact or compact in oc:
            scores.append(0.95)
        else:
            scores.append(0.0)
    return max(scores or [0.0])


def _keyword_score(title, keywords):
    t=_yt_norm(title)
    hits=sum(1 for k in keywords if _yt_norm(k) and _yt_norm(k) in t)
    return min(1.0, hits / max(1, min(2,len(keywords))))


def auto_choose_youtube(results, source_title, cfg):
    """Score YouTube search results for official movie video-song selection.

    The score deliberately prefers configured official music channels and titles containing
    phrases such as 'video song' / 'full video song'. The original playlist title remains
    the strongest semantic signal so similarly named songs are not accidentally selected.
    """
    a=cfg.get('automation',{})
    keywords=a.get('auto_youtube_keywords', ['video song','full video song'])
    official=a.get('auto_youtube_official_channels', [])
    weights=(a.get('auto_youtube_title_weight',.35),a.get('auto_youtube_keyword_weight',.22),
             a.get('auto_youtube_channel_weight',.28),a.get('auto_youtube_duration_weight',.10))
    import difflib
    rows=[]
    src=_yt_norm(source_title)
    for r in results:
        title=_yt_norm(r.get('title'))
        title_score=difflib.SequenceMatcher(None,src,title).ratio()
        kw=_keyword_score(r.get('title',''),keywords)
        ch=_channel_match(r.get('channel',''),official)
        # A small bonus for recognizable official-video wording.
        video_bonus=0.05 if re.search(r'(?i)\bfull\s+video\s+song\b',r.get('title','')) else 0.0
        score=weights[0]*title_score+weights[1]*kw+weights[2]*ch+video_bonus
        rows.append((score,r,title_score,kw,ch))
    rows.sort(key=lambda x:x[0],reverse=True)
    return rows


def choose(results):
    print('\\nTop YouTube results:')
    for i, r in enumerate(results, 1):
        print(f'[{i}] {r["title"]} | {r.get("channel", "")} | {r["url"]}')
    while True:
        x = input(f'Choose YouTube result [1-{len(results)}], or s=skip, q=quit: ').strip().lower()
        if x == 's': return 'skip'
        if x == 'q': return 'quit'
        if x.isdigit() and 1 <= int(x) <= len(results): return results[int(x) - 1]


def choose_youtube(results, source_title, cfg):
    a=cfg.get('automation',{})
    if not a.get('auto_youtube_selection',False):
        return choose(results)
    ranked=auto_choose_youtube(results,source_title,cfg)
    if not ranked:
        raise RuntimeError('Automatic YouTube selection found no candidates.')
    print('\\nAUTO YouTube selection:')
    for i,(score,r,ts,kw,ch) in enumerate(ranked[:min(5,len(ranked))],1):
        print(f'[{i}] score={score:.3f} | title={ts:.3f} keyword={kw:.3f} official_channel={ch:.3f} | {r["title"]} | {r.get("channel","")}')
    selected=ranked[0][1].copy()
    selected['auto_score']=ranked[0][0]
    selected['auto_score_parts']={'title':ranked[0][2],'keywords':ranked[0][3],'official_channel':ranked[0][4]}
    print(f'AUTO selected YouTube: {selected["title"]} | {selected.get("channel","")} | score={ranked[0][0]:.3f}')
    return selected

def info(url):
    code, out, err = run(['yt-dlp', '--dump-single-json', '--skip-download', '--quiet', '--no-warnings', url])
    if code:
        raise RuntimeError(err or out)
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'Video metadata JSON parse failed: {e}\n{out[:2000]}\n{err[:2000]}')


def download(url, staging):
    staging = Path(staging)
    staging.mkdir(parents=True, exist_ok=True)
    outtmpl = str(staging / '%(title)s [%(id)s].%(ext)s')
    code, out = run(['yt-dlp', '-f', 'bv*+ba/b', '--merge-output-format', 'mp4', '--no-playlist', '-o', outtmpl, url], True)
    if code:
        raise RuntimeError(out)
    files = list(staging.glob('*.mp4'))
    if not files:
        raise RuntimeError('yt-dlp completed but no MP4 was produced')
    return max(files, key=lambda p: p.stat().st_size)


def metadata_clues(d):
    """Extract title, likely artists, movie/album clues and duration from the selected YouTube video."""
    title = d.get('title', '')
    desc = d.get('description') or ''
    uploader = d.get('uploader') or d.get('channel') or ''
    album = d.get('album') or ''

    parts = [p.strip() for p in re.split(r'[|•]', title) if p.strip()]
    generic = {
        'video song', 'video', 'audio song', 'full video', 'full song', 'official',
        'lyrical video', 'lyrics', 'song', '4k', '8k', 'hd', 'telugu', 'telugu songs',
        'latest', 'new song', 'full lyrical video'
    }

    title_core = parts[0] if parts else title
    clue_parts = [p for p in parts[1:] if p.lower() not in generic and len(p) >= 2]

    movie_candidates = []
    # Many official Telugu uploads use: 'MOVIE - SONG ...'. If the second dash segment
    # is not just a format keyword, treat it as the actual song title and the first segment
    # as the movie name. This fixes searches such as 'Atithi Devo Bhava - Baguntundhi Nuvvu Navvithe'.
    dash_parts=[x.strip() for x in re.split(r'\s+[-–—:]\s+', title) if x.strip()]
    if len(dash_parts) >= 2 and len(parts) == 1:
        first, second = dash_parts[0], dash_parts[1]
        second_clean=re.sub(r'(?i)\b(?:full\s+)?(?:video\s+song|video|audio\s+song|lyric(?:al)?(?:\s+video)?|lyrics|official|4k|8k|hd)\b',' ',second)
        second_clean=re.sub(r'\s+',' ',second_clean).strip(' -|')
        if second_clean and len(second_clean.split()) >= 2:
            title_core = second_clean
            movie_candidates.append(first)
        elif not parts:
            title_core = first

    artist_candidates = []
    if clue_parts:
        first_clue=clue_parts[0].strip()
        if first_clue and first_clue.lower() not in generic and len(first_clue) >= 2:
            movie_candidates.append(first_clue)

    # Common Telugu music-video title patterns: Movie first, then actors/composer/singers/channel.
    for p in clue_parts:
        lp = p.lower()
        if any(k in lp for k in ('movie', 'film', 'from ')):
            movie_candidates.append(p)
        elif lp in {'saregama telugu', 'aditya music', 't-series telugu', 'lahari music', 'sony music south', 'tips telugu'}:
            continue
        else:
            artist_candidates.append(p)

    for pat in [
        r'(?i)(?:movie|film|from)\s*[:\-]\s*([^\n|]+)',
        r'(?i)([A-Za-z0-9 .&()]+)\s*\(Original Motion Picture Soundtrack\)',
        r'(?i)from\s*["“]?([^"”|\n]+)',
    ]:
        for m in re.finditer(pat, desc + ' ' + album):
            movie_candidates.append(m.group(1).strip())

    # Album itself is a useful movie clue for soundtrack releases.
    if album and ('soundtrack' in album.lower() or 'motion picture' in album.lower()):
        movie_candidates.append(album)

    # Preserve old generic movie_candidates behavior for compatibility, but now separately expose artists.
    seen = set()
    movies = []
    for x in movie_candidates:
        k = x.lower().strip()
        if k and k not in seen:
            seen.add(k)
            movies.append(x)

    seen = set()
    artists = []
    for x in artist_candidates:
        k = x.lower().strip()
        if k and k not in seen:
            seen.add(k)
            artists.append(x)

    if uploader and uploader.lower() not in {x.lower() for x in artists}:
        # Uploader is retained separately; it should not dominate Spotify ranking.
        pass

    return {
        'title': title_core or title,
        'full_youtube_title': title,
        'artist': artists[0] if artists else uploader,
        'artist_candidates': artists,
        'album': album,
        'movie_candidates': movies,
        'duration': d.get('duration'),
        'channel': d.get('channel') or uploader or '',
        'uploader': uploader,
        'release_date': d.get('upload_date'),
        'description': desc,
    }
