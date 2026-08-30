import base64, hashlib, json, os, re, secrets, subprocess, sys, time, webbrowser, threading
from pathlib import Path
import requests
from rapidfuzz.fuzz import ratio, token_set_ratio, WRatio

_TOKEN_CACHE = {"token": None, "expires_at": 0.0, "refresh_token": None}

SCOPES = "playlist-read-private playlist-read-collaborative"

def _redirect_uri():
    return os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback").strip()

def _oauth_cache_path():
    return Path(os.getenv("SPOTIFY_OAUTH_CACHE", "state/spotify_oauth.json"))

def _pkce_pair():
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge

def _save_oauth(data):
    p=_oauth_cache_path(); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _load_oauth():
    p=_oauth_cache_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _authorization_code_token():
    cid, secret = _credentials()
    cached = _load_oauth() or {}
    if cached.get("refresh_token"):
        r=requests.post("https://accounts.spotify.com/api/token", data={
            "grant_type":"refresh_token", "refresh_token":cached["refresh_token"],
            "client_id":cid
        }, timeout=20)
        if r.ok:
            data=r.json(); data["refresh_token"]=data.get("refresh_token") or cached["refresh_token"]; _save_oauth(data)
            return data.get("access_token"), time.time()+float(data.get("expires_in",3600))
    verifier, challenge = _pkce_pair()
    state=secrets.token_urlsafe(24)
    params={"response_type":"code","client_id":cid,"scope":SCOPES,"redirect_uri":_redirect_uri(),"state":state,"code_challenge_method":"S256","code_challenge":challenge}
    auth_url="https://accounts.spotify.com/authorize?" + requests.compat.urlencode(params)
    received={}; ready=threading.Event()
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            q=parse_qs(urlparse(self.path).query)
            received.update({k:v[0] for k,v in q.items() if v})
            self.send_response(200); self.send_header("Content-Type","text/plain; charset=utf-8"); self.end_headers(); self.wfile.write(b"Spotify authorization received. You can close this window.")
            ready.set()
        def log_message(self,*args): pass
    parsed=requests.compat.urlparse(_redirect_uri())
    server=HTTPServer((parsed.hostname or "127.0.0.1", parsed.port or 8888), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    print("\nSpotify authorization required for playlist access.", flush=True)
    print("  Open/login URL:", auth_url, flush=True)
    webbrowser.open(auth_url)
    if not ready.wait(timeout=180):
        server.server_close(); raise RuntimeError("Spotify authorization timed out after 180 seconds.")
    server.server_close()
    if received.get("state") != state: raise RuntimeError("Spotify authorization failed: invalid state.")
    if received.get("error"): raise RuntimeError("Spotify authorization failed: " + received["error"])
    code=received.get("code")
    if not code: raise RuntimeError("Spotify authorization failed: no authorization code received.")
    r=requests.post("https://accounts.spotify.com/api/token", data={"grant_type":"authorization_code","code":code,"redirect_uri":_redirect_uri(),"client_id":cid,"code_verifier":verifier}, timeout=20)
    if not r.ok: raise RuntimeError(f"Spotify authorization-code exchange failed: HTTP {r.status_code}: {r.text[:1000]}")
    data=r.json(); _save_oauth(data)
    return data.get("access_token"), time.time()+float(data.get("expires_in",3600))


def norm(s):
    return re.sub(r"[^\w]+", " ", str(s or "").lower(), flags=re.UNICODE).strip()


def song_key(song):
    artists = song.get("artists") or []
    if isinstance(artists, list):
        artists = " ".join(artists)
    return "|".join([
        norm(song.get("name") or song.get("title")),
        norm(artists),
        norm(song.get("album_name") or song.get("album")),
    ])


def _credentials():
    cid = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    if not cid or cid.startswith("YOUR_"):
        raise RuntimeError("SPOTIFY_CLIENT_ID is missing from .env")
    if not secret or secret.startswith("YOUR_"):
        raise RuntimeError("SPOTIFY_CLIENT_SECRET is missing from .env")
    return cid, secret


def _token():
    now=time.time()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"]-30:
        return _TOKEN_CACHE["token"]
    token, expires = _authorization_code_token()
    if not token: raise RuntimeError("Spotify authentication failed: no access token returned.")
    _TOKEN_CACHE.update(token=token, expires_at=expires)
    return token


def _get(url, params=None):
    token = _token()
    r = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code == 401:
        _TOKEN_CACHE.update(token=None, expires_at=0)
        token = _token()
        r = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if not r.ok:
        raise RuntimeError(f"Spotify API failed: HTTP {r.status_code}: {r.text[:1500]}")
    return r.json()


def playlist_id(value):
    s = str(value or "").strip()
    m = re.search(r"spotify\.com/playlist/([A-Za-z0-9]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", s):
        return s
    raise RuntimeError("Invalid spotify_playlist_url. Use an open.spotify.com/playlist/... URL or playlist ID.")


def _track(item):
    t = ((item.get("item") or item.get("track")) if isinstance(item, dict) else None)
    if not t or not t.get("id"):
        return None
    artists = [a.get("name", "") for a in (t.get("artists") or [])]
    album = t.get("album") or {}
    return {
        "name": t.get("name") or "",
        "title": t.get("name") or "",
        "artists": artists,
        "album_name": album.get("name") or "",
        "album": album.get("name") or "",
        "duration": (float(t.get("duration_ms", 0)) / 1000.0) if t.get("duration_ms") else None,
        "duration_ms": t.get("duration_ms"),
        "url": (t.get("external_urls") or {}).get("spotify") or f"https://open.spotify.com/track/{t['id']}",
        "song_id": t.get("id") or "",
        "spotify_id": t.get("id") or "",
        "isrc": ((t.get("external_ids") or {}).get("isrc") or "").strip().upper() or None,
        "release_date": album.get("release_date"),
        "popularity": t.get("popularity"),
        "artwork_url": ((album.get("images") or [{}])[0].get("url") if album.get("images") else None),
    }


def playlist(url_or_id):
    pid = playlist_id(url_or_id)
    data = _get(f"https://api.spotify.com/v1/playlists/{pid}", params={"fields": "id,name,external_urls(spotify)"})
    title = data.get("name") or pid
    rows = []
    offset = 0
    while True:
        page = _get(f"https://api.spotify.com/v1/playlists/{pid}/items", params={"limit": 50, "offset": offset})
        items = page.get("items") or []
        for item in items:
            track = _track(item)
            if track:
                rows.append(track)
        if not page.get("next"):
            break
        offset += len(items)
    return pid, title, rows


def search(query, limit=10):
    data = _get("https://api.spotify.com/v1/search", {"q": query, "type": "track", "limit": max(1, min(int(limit), 50))})
    return [_track({"track": x}) for x in (data.get("tracks", {}).get("items") or []) if _track({"track": x})]


def _duration_score(a, b):
    try:
        return max(0.0, 1.0 - abs(float(a) - float(b)) / max(float(a), float(b), 1.0))
    except Exception:
        return 0.0


def rank(results, title, artists="", album="", duration=None, cfg=None):
    w = (cfg or {}).get("spotify_search", {})
    artist_text = artists if isinstance(artists, str) else " ".join(artists or [])
    out = []
    for r in results:
        rt = r.get("name") or r.get("title") or ""
        ra = r.get("artists") or []
        ra = " ".join(ra) if isinstance(ra, list) else str(ra)
        al = r.get("album_name") or r.get("album") or ""
        ts = max(ratio(norm(title), norm(rt)), token_set_ratio(norm(title), norm(rt)), WRatio(norm(title), norm(rt))) / 100
        ars = ratio(norm(artist_text), norm(ra)) / 100 if artist_text else 0
        als = max(ratio(norm(album), norm(al)) / 100, token_set_ratio(norm(album), norm(al)) / 100) if album else 0
        ds = _duration_score(duration, r.get("duration"))
        score = w.get("title_weight", .5) * ts + w.get("artist_weight", .25) * ars + w.get("album_weight", .15) * als + w.get("duration_weight", .1) * ds
        out.append({"rank": 0, "score": round(score, 6), "title_score": ts, "artist_score": ars, "album_score": als, "duration_score": ds, "result": r})
    out.sort(key=lambda x: x["score"], reverse=True)
    for i, x in enumerate(out, 1): x["rank"] = i
    return out


def choose(ranked, mode="automatic"):
    if not ranked:
        raise RuntimeError("No Spotify search results.")
    if mode == "automatic":
        return ranked[0]["result"], ranked
    for x in ranked[:5]:
        r = x["result"]
        print(f"[{x['rank']}] score={x['score']:.3f} | {r['name']} | {', '.join(r['artists'])} | {r['album_name']} | {r['url']}", flush=True)
    while True:
        a = input("Choose Spotify result 1-5, or q to cancel: ").strip().lower()
        if a == "q": raise KeyboardInterrupt
        if a.isdigit() and 1 <= int(a) <= min(5, len(ranked)):
            return ranked[int(a)-1]["result"], ranked


def _spotdl_command():
    return [sys.executable, "-m", "spotdl"]


def download(song, cfg, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    url = song.get("url")
    if not url:
        raise RuntimeError("Spotify track has no URL.")
    cid, secret = _credentials()
    archive = out / ".spotdl_archive.txt"; errors = out / ".spotdl_errors.txt"
    archive.touch(exist_ok=True); errors.touch(exist_ok=True)
    cmd = _spotdl_command() + [
        "download", url,
        "--format", cfg.get("spotify_output_format", "mp3"),
        "--output", str(out / "{title}.{output-ext}"),
        "--overwrite", "force",
        "--archive", str(archive),
        "--save-errors", str(errors),
        "--print-errors", "--simple-tui", "--log-level", "WARNING",
        "--threads", "1", "--client-id", cid, "--client-secret", secret,
    ]
    print("  spotDL: downloading selected Spotify recording ...", flush=True)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", cwd=str(Path.cwd()))
    text = p.stdout or ""
    if p.returncode:
        raise RuntimeError(f"spotDL failed for {url}\n{text[-12000:]}")
    candidates = [p for p in out.iterdir() if p.suffix.lower() in {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav"} and not p.name.startswith(".")]
    if not candidates:
        raise RuntimeError(f"spotDL reported success but no audio file was produced for {url}.\n{text[-6000:]}")
    audio = max(candidates, key=lambda p: p.stat().st_mtime)
    artwork = next((p for p in out.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}), None)
    return audio, artwork
