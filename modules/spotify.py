import os, subprocess, json, shutil, re, sys
from pathlib import Path
from rapidfuzz import fuzz
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.mp4 import MP4, MP4Cover


def client():
    cid = os.getenv('SPOTIPY_CLIENT_ID')
    secret = os.getenv('SPOTIPY_CLIENT_SECRET')
    if not cid or not secret or cid.startswith('YOUR_') or secret.startswith('YOUR_'):
        raise RuntimeError('Set real SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET before running the pipeline.')
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret))


def norm(s):
    return re.sub(r'[^a-z0-9\u0C00-\u0C7F]+', ' ', (s or '').lower()).strip()


def _duration_score(a, b):
    if a is None or b is None:
        return 0.0
    try:
        diff = abs(float(a) - float(b))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, 1.0 - diff / 20.0)


def _safe_error(e):
    return str(e).replace('\x00', ' ')


def search_top5(clues):
    """Return at most five Spotify recordings ranked using YouTube metadata."""
    sp = client()
    title = clues.get('title', '')
    artist = clues.get('artist', '')
    artist_candidates = clues.get('artist_candidates') or []
    movies = clues.get('movie_candidates') or []
    album = clues.get('album', '')

    queries = []
    for q in [
        f'{title} {artist}',
        *[f'{title} {a}' for a in artist_candidates[:6]],
        f'{title} {album}',
        *[f'{title} {m}' for m in movies[:5]],
        title,
    ]:
        q = ' '.join(q.split())
        if q and q not in queries:
            queries.append(q)

    candidates = {}
    errors = []
    for q in queries:
        try:
            # Spotify's API currently accepts a maximum of 10 per request.
            items = sp.search(q=q, type='track', limit=10).get('tracks', {}).get('items', [])
        except Exception as e:
            errors.append(f'{q!r}: {_safe_error(e)}')
            continue
        for x in items:
            candidates[x['id']] = x

    if not candidates:
        detail = '\n'.join(errors[-3:])
        raise RuntimeError('Spotify returned no candidates.' + (f'\n{detail}' if detail else ''))

    scored = []
    title_n = norm(title)
    artist_n = norm(artist)
    album_n = norm(album)
    movie_n = [norm(m) for m in movies if m]
    a=clues.get('automation',{}) or {}
    scored = []
    soundtrack_phrases = [
        'original motion picture soundtrack', 'original soundtrack',
        'motion picture soundtrack', 'original movie soundtrack', 'film soundtrack'
    ]
    for x in candidates.values():
        xt = norm(x.get('name'))
        xa = norm(' '.join(a.get('name', '') for a in x.get('artists', [])))
        alb_raw = x.get('album', {}).get('name','') or ''
        alb = norm(alb_raw)
        title_score = fuzz.token_set_ratio(title_n, xt) / 100 if title_n else 0
        artist_score = max([fuzz.token_set_ratio(norm(a0), xa) / 100 for a0 in ([artist] + artist_candidates) if a0] or [0])
        movie_score = max([fuzz.token_set_ratio(m, alb) / 100 for m in movie_n] or [0])
        album_score = fuzz.token_set_ratio(album_n, alb) / 100 if album_n else 0
        dur_score = _duration_score(clues.get('duration'), (x.get('duration_ms') or 0) / 1000)
        exact_movie = 0.0
        for m in movie_n:
            if m and (m == alb or m in alb or alb in m):
                exact_movie = 1.0
                break
        ost = 1.0 if any(norm(ph) in alb for ph in soundtrack_phrases) else 0.0
        # Movie/OST evidence is intentionally weighted strongly. This prevents a popular
        # same-title compilation or playlist-style release from outranking the actual film soundtrack.
        base = .34*title_score + .18*artist_score + .18*max(movie_score,album_score) + .12*dur_score
        score = base + float(a.get('auto_spotify_movie_album_bonus',.20))*movie_score
        score += float(a.get('auto_spotify_ost_bonus',.12))*ost
        score += float(a.get('auto_spotify_exact_album_bonus',.10))*exact_movie
        score = min(score, 1.0)
        scored.append((score, x, title_score, artist_score, max(movie_score, album_score), dur_score, ost, exact_movie))

    scored.sort(key=lambda z: z[0], reverse=True)
    out = []
    for score, x, ts, as_, mas, ds, ost, exact_movie in scored[:5]:
        details = sp.track(x['id'])
        isrc = (details.get('external_ids') or {}).get('isrc')
        out.append({
            'id': x['id'],
            'url': x['external_urls']['spotify'],
            'title': x['name'],
            'artist': ', '.join(a['name'] for a in x.get('artists', [])),
            'album': x['album']['name'],
            'album_artist': (x['album'].get('artists') or [{}])[0].get('name', ''),
            'release_date': x['album'].get('release_date'),
            'duration': (x.get('duration_ms') or 0) / 1000,
            'isrc': isrc,
            'artwork_url': (x['album'].get('images') or [{}])[0].get('url'),
            'score': score,
            'score_parts': {'title': ts, 'artist': as_, 'movie_album': mas, 'duration': ds, 'original_soundtrack_album': ost, 'exact_or_contains_movie_album': exact_movie},
            'raw': details,
        })
    return out


def choose_top5(results, cfg=None):
    cfg=cfg or {}
    auto=cfg.get('automation',{})
    print('\nTop 5 Spotify matches — YOU choose the exact recording:' if not auto.get('auto_spotify_selection',False) else '\nTop 5 Spotify matches — automatic mode:')
    if not auto.get('auto_spotify_selection',False):
        print('The score is only a ranking aid. Check movie/album, artist, duration and ISRC.')
    for i, r in enumerate(results, 1):
        mins = int(r['duration'] // 60); secs = int(r['duration'] % 60)
        print(f'[{i}] {r["title"]} — {r["artist"]} | album: {r["album"]} | year: {(r.get("release_date") or "")[:4]} | duration: {mins}:{secs:02d} | ISRC: {r.get("isrc") or "N/A"} | score={r["score"]:.3f}')
        print(f'     {r["url"]}')
    if auto.get('auto_spotify_selection',False):
        if not results or not results[0].get('isrc'):
            raise RuntimeError('Automatic Spotify selection has no valid ISRC candidate.')
        threshold=float(auto.get('auto_spotify_min_score',0.55))
        if float(results[0].get('score',0)) < threshold:
            raise RuntimeError(f'Best automatic Spotify match score {results[0].get("score",0):.3f} is below configured minimum {threshold:.3f}.')
        print(f'AUTO selected Spotify: {results[0]["title"]} — {results[0]["artist"]} | {results[0]["album"]} | ISRC={results[0]["isrc"]} | score={results[0]["score"]:.3f}')
        return results[0]
    while True:
        x = input('Choose Spotify result [1-5], or s=skip, q=quit: ').strip().lower()
        if x == 's': return 'skip'
        if x == 'q': return 'quit'
        if x.isdigit() and 1 <= int(x) <= len(results):
            r = results[int(x) - 1]
            if not r.get('isrc'):
                print('Selected Spotify result has no ISRC. Choose another result.')
                continue
            return r

def _collect_files(temp):
    temp = Path(temp)
    m4as = [p for p in temp.rglob('*') if p.is_file() and p.suffix.lower() == '.m4a']
    lrcs = [p for p in temp.rglob('*') if p.is_file() and p.suffix.lower() == '.lrc']
    return m4as, lrcs


def _run_command(cmd, log, label):
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        text = p.stdout or ''
    except Exception as e:
        p = None
        text = f'Exception while starting command: {e}'
    with Path(log).open('a', encoding='utf-8') as f:
        f.write(f'\n===== {label} =====\n')
        f.write('COMMAND: ' + ' '.join(map(str, cmd)) + '\n')
        f.write(text)
        f.write('\n')
    return p, text


def _run_spotdl(url, temp, cfg, selected):
    """Resilient SpotDL downloader.

    SpotDL is tried several ways using the SAME interpreter as main.py. A partial
    successful M4A is accepted even if SpotDL exits non-zero while fetching lyrics.
    If SpotDL itself cannot obtain audio, yt-dlp is used as a last-resort resolver,
    which is effectively the same YouTube source SpotDL uses internally.
    """
    temp = Path(temp)
    temp.mkdir(parents=True, exist_ok=True)
    log = temp / 'spotdl_stdout.log'
    if log.exists():
        log.unlink()

    # Use a directory, not a fragile output template. This is more compatible with spotdl 4.5.x.
    base = [
        sys.executable, '-m', 'spotdl', 'download', url,
        '--format', 'm4a',
        '--bitrate', cfg.get('spotdl_bitrate', 'auto'),
        '--output', str(temp),
        '--overwrite', 'force',
    ]

    attempts = [
        (base + ['--use-official-api', '--lyrics', 'synced', '--generate-lrc'], 'Attempt 1: official API + synced LRC'),
        (base + ['--lyrics', 'synced', '--generate-lrc'], 'Attempt 2: normal API + synced LRC'),
        (base + ['--use-official-api'], 'Attempt 3: official API audio only'),
        (base, 'Attempt 4: SpotDL audio only'),
    ]

    for cmd, label in attempts:
        _run_command(cmd, log, label)
        m4as, lrcs = _collect_files(temp)
        if m4as:
            # Prefer the largest audio file; ignore temporary/partial files.
            return max(m4as, key=lambda p: p.stat().st_size), (lrcs[0] if lrcs else None)

    # Final fallback: resolve the Spotify-selected recording from YouTube using the
    # exact metadata the user selected. This prevents a broken SpotDL invocation from
    # killing the whole queue.
    query = f'{selected.get("artist", "")} {selected.get("title", "")} {selected.get("album", "")}'.strip()
    fallback = [
        sys.executable, '-m', 'yt_dlp',
        f'ytsearch1:{query}',
        '--no-playlist',
        '--extract-audio',
        '--audio-format', 'm4a',
        '--audio-quality', '0',
        '-o', str(temp / '%(title)s.%(ext)s'),
    ]
    _run_command(fallback, log, 'Attempt 5: yt-dlp metadata fallback')
    m4as, lrcs = _collect_files(temp)
    if not m4as:
        raise RuntimeError(f'SpotDL failed to produce an M4A after all retries. See {log}')
    return max(m4as, key=lambda p: p.stat().st_size), (lrcs[0] if lrcs else None)


def _download_art(url, path):
    if not url:
        return None
    import requests
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.content
    # Correct extension based on image signature instead of assuming JPEG.
    if data.startswith(b'\x89PNG'):
        path = Path(path).with_suffix('.png')
    else:
        path = Path(path).with_suffix('.jpg')
    path.write_bytes(data)
    return path


def _find_final_audio(final_root, isrc):
    """Find an already-finalized M4A in songs/final by its embedded ISRC."""
    root = Path(final_root)
    if not root.exists():
        return None
    for p in root.glob('*.m4a'):
        try:
            m = MP4(str(p))
            tags = m.tags or {}
            vals = tags.get('----:com.apple.iTunes:ISRC') or []
            decoded = []
            for v in vals:
                if isinstance(v, bytes):
                    decoded.append(v.decode('utf-8', errors='ignore'))
                else:
                    decoded.append(str(v))
            if isrc in decoded or isrc in str(tags.get('\xa9cmt', '')):
                return p
        except Exception:
            continue
    return None


def _extract_embedded_lyrics(audio, temp):
    try:
        m = MP4(str(audio))
        vals = (m.tags or {}).get('\xa9lyr') or []
        if not vals:
            return None
        text = vals[0].decode('utf-8', errors='ignore') if isinstance(vals[0], bytes) else str(vals[0])
        if not text.strip():
            return None
        out = Path(temp) / 'embedded_lyrics.lrc'
        out.write_text(text, encoding='utf-8')
        return out
    except Exception:
        return None


def _embed_metadata(audio, selected, art, lrc):
    """Embed all useful Spotify metadata into the M4A itself.

    No final-sidecar metadata, artwork, or lyrics files are required. Lyrics are
    embedded only when a valid LRC is actually available.
    """
    m = MP4(str(audio))
    tags = m.tags or m.add_tags()
    tags['\xa9nam'] = [selected['title']]
    tags['\xa9ART'] = [selected['artist']]
    tags['\xa9alb'] = [selected['album']]
    if selected.get('album_artist'):
        tags['aART'] = [selected['album_artist']]
    if selected.get('release_date'):
        tags['\xa9day'] = [selected['release_date']]
    tags['\xa9cmt'] = [json.dumps({
        'isrc': selected.get('isrc'),
        'spotify_url': selected.get('url'),
        'lyrics_embedded': bool(lrc and Path(lrc).exists()),
        'source': 'audio-shorts-generator',
    }, ensure_ascii=False)]
    if selected.get('isrc'):
        tags['----:com.apple.iTunes:ISRC'] = [selected['isrc'].encode('utf-8')]
    if selected.get('id'):
        tags['----:com.apple.iTunes:SpotifyTrackID'] = [selected['id'].encode('utf-8')]
    if selected.get('language'):
        tags['\xa9cmt'] = [tags['\xa9cmt'][0] + ' | language=' + str(selected['language'])]
    if lrc and Path(lrc).exists():
        text = Path(lrc).read_text(encoding='utf-8-sig', errors='ignore')
        if text.strip():
            tags['\xa9lyr'] = [text]
    if art and Path(art).exists():
        ext = Path(art).suffix.lower()
        fmt = MP4Cover.FORMAT_PNG if ext == '.png' else MP4Cover.FORMAT_JPEG
        tags['covr'] = [MP4Cover(Path(art).read_bytes(), imageformat=fmt)]
    m.save()


def _safe_filename(selected):
    safe = re.sub(r'[<>:"/\\|?*]+', '_', f"{selected['artist']} - {selected['title']}").strip()
    safe = re.sub(r'\s+', ' ', safe).rstrip('.')
    isrc = re.sub(r'[^A-Za-z0-9._-]+', '_', selected.get('isrc') or 'NOISRC')
    return f'{safe} [{isrc}].m4a'


def download_and_finalize(selected, temp, final_root, cfg):
    temp = Path(temp)
    final_root = Path(final_root)
    final_root.mkdir(parents=True, exist_ok=True)

    # Resume safely from a root-level final M4A. No ISRC subfolder is used.
    existing = _find_final_audio(final_root, selected['isrc'])
    if existing:
        embedded_lrc = _extract_embedded_lyrics(existing, temp)
        meta = temp / 'spotify_metadata.json'
        meta.write_text(json.dumps({k:v for k,v in selected.items() if k != 'raw'}, ensure_ascii=False, indent=2), encoding='utf-8')
        return existing, embedded_lrc, meta, None

    audio, lrc = _run_spotdl(selected['url'], temp, cfg, selected)
    art = _download_art(selected.get('artwork_url'), temp / 'artwork.jpg') if selected.get('artwork_url') else None
    meta = {k: v for k, v in selected.items() if k != 'raw'}
    meta['lyrics_status'] = 'available' if lrc and Path(lrc).exists() and Path(lrc).read_text(encoding='utf-8-sig', errors='ignore').strip() else 'unavailable'
    meta['download_source'] = 'spotdl_with_resilient_fallbacks'
    meta['lyrics_policy'] = 'skip lyrics when Spotify synced lyrics are unavailable'
    (temp / 'spotify_metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

    # A lyric file is only used if it really contains timed/text content.
    if not (lrc and Path(lrc).exists() and Path(lrc).read_text(encoding='utf-8-sig', errors='ignore').strip()):
        lrc = None

    try:
        _embed_metadata(audio, selected, art, lrc)
    except Exception as e:
        raise RuntimeError(f'Could not embed required M4A metadata/artwork/lyrics: {e}') from e

    dest = final_root / _safe_filename(selected)
    shutil.copy2(audio, dest)
    # IMPORTANT: no lyrics/artwork/metadata sidecars are copied to songs/final.
    # Everything requested is embedded in the M4A itself.
    return dest, lrc, meta, art
