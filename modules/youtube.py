import json
import math
import re
import subprocess
import unicodedata
from pathlib import Path


YOUTUBE_WATCH_RE = re.compile(
    r"https?://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]+)"
)
YOUTUBE_SHORT_RE = re.compile(r"https?://youtu\.be/([A-Za-z0-9_-]+)")


def _cookie_args():
    """Use only the explicit home-directory cookie file, when present."""
    cookie_file = Path.home() / "cookies.txt"
    return ["--cookies", str(cookie_file)] if cookie_file.is_file() else []


def clean_url(url):
    """Extract a plain YouTube watch URL from accidental surrounding text."""
    text = str(url or "").strip()
    match = YOUTUBE_WATCH_RE.search(text)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    match = YOUTUBE_SHORT_RE.search(text)
    if match:
        return f"https://youtu.be/{match.group(1)}"
    return text


def _run(args):
    cmd = ["yt-dlp", "--ignore-config", *_cookie_args(), *args]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "yt-dlp was not found. Install it in the active environment."
        ) from exc
    return proc.returncode, proc.stdout


def playlist(url):
    code, output = _run([
        "--flat-playlist",
        "--dump-single-json",
        "--skip-download",
        "--quiet",
        "--no-warnings",
        clean_url(url),
    ])
    if code:
        raise RuntimeError(output[-8000:] or "yt-dlp playlist discovery failed.")

    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("yt-dlp returned invalid playlist JSON.") from exc

    rows = []
    for index, entry in enumerate(data.get("entries") or [], 1):
        if not entry:
            continue
        video_id = entry.get("id")
        if not video_id:
            continue
        rows.append({
            "playlist_index": index,
            "title": entry.get("title") or "",
            "id": video_id,
            "url": clean_url(
                entry.get("webpage_url")
                or f"https://www.youtube.com/watch?v={video_id}"
            ),
        })
    return rows


def search(query, count=10):
    code, output = _run([
        f"ytsearch{int(count)}:{query}",
        "--flat-playlist",
        "--dump-json",
        "--skip-download",
        "--quiet",
        "--no-warnings",
    ])
    if code:
        raise RuntimeError(output[-8000:] or "yt-dlp YouTube search failed.")

    rows = []
    for line in output.splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        video_id = data.get("id")
        if not video_id:
            continue

        rows.append({
            "id": video_id,
            "url": clean_url(
                data.get("webpage_url")
                or f"https://www.youtube.com/watch?v={video_id}"
            ),
            "title": data.get("title") or "",
            "channel": data.get("channel") or data.get("uploader") or "",
            "uploader": data.get("uploader"),
            "duration": data.get("duration"),
            "view_count": data.get("view_count"),
            "upload_date": data.get("upload_date"),
        })
    return rows


def _norm(value):
    """Normalize titles without discarding non-Latin Unicode letters."""
    text = unicodedata.normalize("NFKC", value or "").lower()
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def _compact(value):
    """Normalize spacing/repeated-letter spelling variants for song titles."""
    text = unicodedata.normalize("NFKC", value or "").lower()
    text = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    # Handles common YouTube spelling variants such as
    # "Koppamga" vs "Kopam Ga" without changing the displayed title.
    return re.sub(r"(.)\1+", r"\1", text)


def _source_song_core(value):
    """
    Extract the meaningful song-title part from a playlist title.

    Examples:
      Koppamga Koppamga (From "Mr. Majnu") -> Koppamga Koppamga
      Urike Urike -> Urike Urike
    """
    raw = unicodedata.normalize("NFKC", value or "")
    raw = re.sub(r"\s*\(\s*from\b[^)]*\)", " ", raw, flags=re.I)
    raw = re.sub(r"\s*\[\s*from\b[^\]]*\]", " ", raw, flags=re.I)
    normalized = _norm(raw)
    # "From ..." is a wrapper in playlist/streaming titles, not part of
    # the song name used to identify the YouTube music video.
    normalized = re.sub(r"\bfrom\b.*$", "", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def _title_score(query, title):
    from rapidfuzz.fuzz import ratio, token_set_ratio, WRatio

    q = _source_song_core(query)
    t = _norm(title)
    if not q or not t:
        return 0.0

    q_compact = _compact(q)
    t_compact = _compact(t)

    # Exact core-song match is the strongest signal. This prevents a result
    # such as "Urike Chilaka" from being treated as an exact match for
    # "Urike Urike" merely because one token overlaps.
    if q_compact and q_compact in t_compact:
        return 1.0

    query_tokens = q.split()
    title_tokens = set(t.split())
    overlap = (
        sum(1 for token in query_tokens if token in title_tokens)
        / max(1, len(query_tokens))
    )

    fuzzy = max(
        ratio(q, t),
        token_set_ratio(q, t),
        WRatio(q, t),
    ) / 100.0
    compact_fuzzy = ratio(q_compact, t_compact) / 100.0

    # A fuzzy match is allowed to tolerate punctuation, spacing and minor
    # spelling differences, but partial-token matches are capped.
    score = max(fuzzy * 0.90, compact_fuzzy)
    if overlap < 1.0:
        score *= 0.75 + 0.25 * overlap
    return min(1.0, score)


def _video_wording_score(title, keywords):
    normalized = _norm(title)

    # Lyrics/audio/alternate versions must not outrank a real video merely
    # because they have more views.
    if re.search(r"\bvideo\s+with\s+lyrics?\b", normalized):
        score = 0.45
    elif re.search(r"\b(?:lyric|lyrics|lyrical)\s+video\b", normalized):
        score = 0.25
    elif re.search(r"\b(?:lyric|lyrics|lyrical)\b", normalized):
        score = 0.20
    elif re.search(r"\bfull\s+video\s+song\b", normalized):
        score = 1.00
    elif re.search(r"\bvideo\s+song\b", normalized):
        score = 0.95
    elif re.search(r"\bfull\s+video\b", normalized):
        score = 0.90
    elif re.search(r"\b(?:official\s+)?(?:music\s+)?video\b", normalized):
        score = 0.85
    else:
        score = 0.0

    for keyword in keywords:
        key = _norm(keyword)
        if not key:
            continue
        if key in normalized:
            if "video song" in key:
                score = max(score, 0.95)
            elif "full video" in key:
                score = max(score, 0.90)

    return score


_QUALITY_PENALTIES = (
    (r"\b(?:slowed|reverb|sped\s*up|nightcore)\b", 0.14, "alternate_speed"),
    (r"\b(?:remix|remastered|8d|8d\s+audio|lofi|lo-fi)\b", 0.12, "alternate_version"),
    (r"\b(?:cover|karaoke|instrumental)\b", 0.20, "cover_or_instrumental"),
    (r"\b(?:bts|behind\s+the\s+scenes|making)\b", 0.22, "behind_the_scenes"),
    (r"\b(?:teaser|trailer|promo|shorts?)\b", 0.24, "promo_or_short"),
    (r"\b(?:audio|audio\s+song)\b", 0.16, "audio_only"),
    (r"\b(?:jukebox|playlist|mix)\b", 0.22, "collection"),
    (r"\b(?:lyric|lyrics|lyrical)\b", 0.12, "lyrics"),
    (r"\b(?:with\s+lyrics?)\b", 0.10, "lyrics"),
)


def _quality_penalty(title):
    normalized = _norm(title)
    penalty = 0.0
    reasons = []
    for pattern, amount, reason in _QUALITY_PENALTIES:
        if re.search(pattern, normalized):
            penalty += amount
            reasons.append(reason)
    return min(0.45, penalty), reasons


def _duration_score(reference_duration, candidate_duration):
    try:
        ref = float(reference_duration)
        cand = float(candidate_duration)
    except (TypeError, ValueError):
        return 0.0

    if ref <= 0 or cand <= 0:
        return 0.0

    difference = abs(ref - cand)
    # Full-song uploads normally have very similar duration. The score
    # degrades smoothly rather than requiring an exact duration.
    return max(0.0, 1.0 - difference / max(ref * 0.25, 5.0))


def rank_results(results, source_title, cfg, reference_info=None):
    keywords = cfg.get("automation", {}).get(
        "auto_youtube_keywords",
        ["full video song", "video song", "full video"],
    )

    max_views = max(
        (int(item.get("view_count") or 0) for item in results),
        default=0,
    )
    reference_duration = (
        reference_info.get("duration")
        if isinstance(reference_info, dict)
        else None
    )

    ranked = []
    for result in results:
        title_match = _title_score(source_title, result["title"])
        wording = _video_wording_score(result["title"], keywords)
        views = int(result.get("view_count") or 0)

        if max_views:
            view_score = min(
                1.0,
                math.log10(views + 1) / math.log10(max_views + 1),
            )
        else:
            view_score = 0.0

        duration_score = _duration_score(
            reference_duration,
            result.get("duration"),
        )
        quality_penalty, penalty_reasons = _quality_penalty(result["title"])

        # Keep title matching dominant, keep real video wording strong, and
        # use views/duration as supporting evidence rather than letting views
        # select a different song.
        score = (
            0.58 * title_match
            + 0.22 * wording
            + 0.10 * view_score
            + 0.10 * duration_score
            - quality_penalty
        )

        # Strong bonus only for an actual full/video-song wording. "Video with
        # Lyrics" does not receive this bonus.
        if re.search(
            r"\b(?:full\s+video\s+song|video\s+song)\b",
            _norm(result["title"]),
        ) and "with lyrics" not in _norm(result["title"]):
            score += 0.06

        ranked.append({
            "rank": 0,
            "score": round(score, 6),
            "title_match": round(title_match, 6),
            "video_wording": round(wording, 6),
            "view_score": round(view_score, 6),
            "view_count": views,
            "duration_score": round(duration_score, 6),
            "quality_penalty": round(quality_penalty, 6),
            "quality_penalty_reasons": penalty_reasons,
            "result": result,
        })

    ranked.sort(
        key=lambda item: (
            item["score"],
            item["title_match"],
            item["video_wording"],
            item["duration_score"],
            item["view_count"],
        ),
        reverse=True,
    )
    for index, item in enumerate(ranked, 1):
        item["rank"] = index
    return ranked


def choose(
    results,
    source_title,
    cfg,
    force_manual=False,
    reference_info=None,
):
    manual = force_manual or not cfg.get("automation", {}).get(
        "auto_youtube_selection", True
    )

    if not manual:
        ranked = rank_results(
            results,
            source_title,
            cfg,
            reference_info=reference_info,
        )
        if not ranked:
            raise RuntimeError("No YouTube search results were returned.")

        print("\nYouTube search results (channel reputation is not considered):")
        for item in ranked:
            result = item["result"]
            print(
                f"[{item['rank']}] score={item['score']:.3f} | "
                f"title_match={item['title_match']:.3f} | "
                f"video_wording={item['video_wording']:.3f} | "
                f"views={result.get('view_count') or 0:,} | "
                f"{result['title']} | {result.get('channel', '')}"
            )

        selected = ranked[0]["result"]
        print("\nAUTO CHOSEN:")
        print(f"[{selected['id']}] {selected['title']}")
        print(f"URL: {selected['url']}", flush=True)
        return selected, ranked

    print("\nTop YouTube results:")
    for index, result in enumerate(results, 1):
        print(
            f"[{index}] {result['title']} | {result.get('channel', '')} | "
            f"views={result.get('view_count') or 0:,} | {result['url']}"
        )

    while True:
        answer = input(
            f"Choose YouTube result [1-{len(results)}], s=skip, q=quit: "
        ).strip().lower()

        if answer == "s":
            return "skip", []
        if answer == "q":
            return "quit", []
        if answer.isdigit() and 1 <= int(answer) <= len(results):
            return results[int(answer) - 1], []

def info(url):
    code, output = _run([
        "--dump-single-json",
        "--skip-download",
        "--quiet",
        "--no-warnings",
        clean_url(url),
    ])
    if code:
        raise RuntimeError(output[-8000:] or "yt-dlp metadata extraction failed.")
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("yt-dlp returned invalid video metadata JSON.") from exc


def download(url, temp_dir, video_id=None):
    temp = Path(temp_dir)
    temp.mkdir(parents=True, exist_ok=True)

    video_id = video_id or _extract_video_id(url)
    output = temp / f"source_{video_id}.%(ext)s"

    code, output_log = _run([
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "-o", str(output),
        clean_url(url),
    ])
    if code:
        raise RuntimeError(output_log[-8000:] or "yt-dlp download failed.")

    exact = temp / f"source_{video_id}.mp4"
    if exact.is_file() and exact.stat().st_size > 0:
        return exact

    candidates = sorted(
        temp.glob(f"source_{video_id}.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate

    raise RuntimeError("yt-dlp completed but no downloaded video file was found.")


def _extract_video_id(url):
    match = YOUTUBE_WATCH_RE.search(str(url or ""))
    if match:
        return match.group(1)
    match = YOUTUBE_SHORT_RE.search(str(url or ""))
    if match:
        return match.group(1)
    return "selected"


def metadata_clues(data):
    return {
        "title": data.get("title", ""),
        "channel": data.get("channel") or data.get("uploader") or "",
        "duration": data.get("duration"),
        "upload_date": data.get("upload_date"),
        "description": data.get("description") or "",
    }
