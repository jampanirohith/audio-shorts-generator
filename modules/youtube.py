import json
import re
import subprocess
from pathlib import Path


def _cookie_args():
    # Only ~/cookies.txt is supported. No Chrome/Edge/Firefox browser-cookie
    # extraction is ever attempted.
    p = Path.home() / "cookies.txt"
    return ["--cookies", str(p)] if p.is_file() else []


def _clean_url(url):
    """Accept a plain YouTube URL and repair accidental surrounding markdown."""
    if not url:
        return url
    m = re.search(r"https?://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+", str(url))
    if m:
        return m.group(0)
    m = re.search(r"https?://youtu\.be/[A-Za-z0-9_-]+", str(url))
    return m.group(0) if m else str(url).strip()


def _run(args, capture=True):
    cmd = ["yt-dlp", "--ignore-config", *_cookie_args(), *args]
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.returncode, p.stdout


def playlist(url):
    # Playlist discovery is intentionally quiet; the main program prints only
    # the current playlist title, not yt-dlp's download/progress stream.
    code, out = _run([
        "--flat-playlist", "--dump-single-json",
        "--skip-download", "--quiet", "--no-warnings", _clean_url(url)
    ])
    if code:
        raise RuntimeError(out[-8000:])
    data = json.loads(out)
    rows = []
    for idx, entry in enumerate(data.get("entries") or [], 1):
        if not entry:
            continue
        vid = entry.get("id")
        rows.append({
            "playlist_index": idx,
            "title": entry.get("title") or "",
            "id": vid,
            "url": entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
        })
    return rows


def search(query, n=10):
    code, out = _run([
        f"ytsearch{n}:{query}",
        "--flat-playlist", "--dump-json", "--skip-download",
        "--quiet", "--no-warnings"
    ])
    if code:
        raise RuntimeError(out[-8000:])
    rows = []
    for line in out.splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        vid = d.get("id")
        if not vid:
            continue
        rows.append({
            "id": vid,
            "url": _clean_url(d.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}"),
            "title": d.get("title") or "",
            "channel": d.get("channel") or d.get("uploader") or "",
            "duration": d.get("duration"),
            "view_count": d.get("view_count"),
            "uploader": d.get("uploader"),
            "upload_date": d.get("upload_date"),
        })
    return rows


def _norm(s):
    return re.sub(r"[^a-z0-9\u0c00-\u0c7f]+", " ", (s or "").lower()).strip()


def _title_score(query, title):
    from rapidfuzz.fuzz import token_set_ratio, ratio
    q, t = _norm(query), _norm(title)
    return max(token_set_ratio(q, t), ratio(q, t)) / 100.0 if q and t else 0.0


def _video_score(title, keywords):
    t = _norm(title)
    if re.search(r"\bfull\s+video\s+song\b", t):
        base = 1.0
    elif re.search(r"\bvideo\s+song\b", t):
        base = 0.95
    elif re.search(r"\bfull\s+video\b", t):
        base = 0.78
    elif re.search(r"\bofficial\s+video\b|\bvideo\b", t):
        base = 0.60
    elif "lyric" in t:
        base = 0.05
    else:
        base = 0.0
    for k in keywords:
        if _norm(k) in t:
            base = max(base, .90 if "video song" in _norm(k) else .70)
    return base


def auto_choose(results, source_title, cfg):
    keywords = cfg.get("automation", {}).get(
        "auto_youtube_keywords",
        ["full video song", "video song", "full video"],
    )
    max_views = max([int(r.get("view_count") or 0) for r in results] or [0])
    ranked = []
    for r in results:
        title_match = _title_score(source_title, r["title"])
        wording = _video_score(r["title"], keywords)
        views = int(r.get("view_count") or 0)
        # Log scale prevents a single viral result from overwhelming a much
        # better title match. Channel/uploader identity is NOT a ranking input.
        view_score = (
            (0.0 if max_views <= 0 else min(1.0, __import__("math").log10(views + 1) / __import__("math").log10(max_views + 1)))
        )
        score = 0.62 * title_match + 0.23 * wording + 0.15 * view_score
        if wording >= .95:
            score += .08
        ranked.append((score, r, title_match, wording, view_score))
    ranked.sort(key=lambda x: (x[0], x[1].get("view_count") or 0), reverse=True)
    return ranked


def choose(results, source_title, cfg):
    if cfg.get("automation", {}).get("auto_youtube_selection", True):
        ranked = auto_choose(results, source_title, cfg)
        if not ranked:
            raise RuntimeError("No YouTube candidates found.")
        print("\nYouTube search results (channel reputation is NOT considered):")
        for i, (score, r, ts, vs, views) in enumerate(ranked, 1):
            print(
                f"[{i}] score={score:.3f} | title_match={ts:.3f} "
                f"video_wording={vs:.3f} views={r.get('view_count') or 0:,} | "
                f"{r['title']} | {r.get('channel','')}"
            )
        selected = ranked[0][1]
        print("\nAUTO CHOSEN:")
        print(f"[{selected['id']}] {selected['title']}")
        print(f"URL: {selected['url']}", flush=True)
        return selected

    print("\nTop YouTube results:")
    for i, r in enumerate(results, 1):
        print(
            f"[{i}] {r['title']} | {r.get('channel','')} | "
            f"views={r.get('view_count') or 0:,} | {r['url']}"
        )
    while True:
        x = input(f"Choose YouTube result [1-{len(results)}], s=skip, q=quit: ").strip().lower()
        if x == "s":
            return "skip"
        if x == "q":
            return "quit"
        if x.isdigit() and 1 <= int(x) <= len(results):
            return results[int(x) - 1]


def info(url):
    code, out = _run([
        "--dump-single-json", "--skip-download", "--quiet",
        "--no-warnings", _clean_url(url)
    ])
    if code:
        raise RuntimeError(out[-8000:])
    return json.loads(out)


def download(url, temp):
    temp = Path(temp)
    temp.mkdir(parents=True, exist_ok=True)
    # Keep all working files directly under temp/.
    out = str(temp / "source [%(id)s].%(ext)s")
    code, outlog = _run([
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--quiet", "--no-warnings",
        "-o", out,
        _clean_url(url),
    ])
    if code:
        raise RuntimeError(outlog[-8000:])
    files = list(temp.glob("source [*].mp4"))
    if not files:
        files = list(temp.glob("*.mp4"))
    if not files:
        raise RuntimeError("yt-dlp finished but no MP4 was produced.")
    return max(files, key=lambda p: p.stat().st_size)


def metadata_clues(d):
    # Kept for compatibility with older project imports.
    return {
        "title": d.get("title", ""),
        "channel": d.get("channel") or d.get("uploader") or "",
        "duration": d.get("duration"),
        "upload_date": d.get("upload_date"),
        "description": d.get("description") or "",
    }
