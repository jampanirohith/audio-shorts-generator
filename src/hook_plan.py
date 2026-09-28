from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
from .scanner import SongPackage, scan_packages
from .utils import Phase3Error, parse_timecode, fmt_ms

DEFAULT_FILENAME = 'hook_timeline.json'


@dataclass(frozen=True)
class HookPlanEntry:
    song_path: Path
    basename: str
    start_ms: int
    end_ms: int
    source_song_path: str
    source_lrc_path: str

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def as_dict(self) -> dict:
        return {
            'song_path': self.source_song_path,
            'lrc_path': self.source_lrc_path,
            'hook': {
                'start': fmt_ms(self.start_ms),
                'end': fmt_ms(self.end_ms),
            },
            'duration_ms': self.duration_ms,
        }


class HookPlan:
    def __init__(self, root: Path, path: Path, entries: list[HookPlanEntry], raw: dict, unconfigured: list[dict] | None = None):
        self.root = root
        self.path = path
        self.entries = entries
        self.unconfigured = unconfigured or []
        self.raw = raw

    @staticmethod
    def _resolve(root: Path, value: str | Path) -> Path:
        p = Path(str(value))
        return (root / p).resolve() if not p.is_absolute() else p.resolve()

    @classmethod
    def fill_from_final(cls, root: Path, path: Path | None = None) -> dict:
        """Populate hook_timeline.json from every MP3 in songs/final.

        Existing hook.start/end values are preserved by exact basename. New songs
        receive blank timelines. The generated entry also records the matching LRC
        path. This command does not choose or infer any hook automatically.
        """
        root = root.resolve()
        path = (path or (root / DEFAULT_FILENAME)).resolve()
        input_dir = root / 'songs' / 'final'
        input_dir.mkdir(parents=True, exist_ok=True)

        existing = {}
        if path.exists():
            try:
                prior = json.loads(path.read_text(encoding='utf-8'))
                prior_songs = prior.get('songs', []) if isinstance(prior, dict) else []
                for item in prior_songs:
                    if not isinstance(item, dict):
                        continue
                    song_path = item.get('song_path')
                    if not song_path:
                        continue
                    try:
                        src = cls._resolve(root, song_path)
                        key = src.stem.lower()
                    except Exception:
                        key = Path(str(song_path)).stem.lower()
                    hook = item.get('hook') if isinstance(item.get('hook'), dict) else item
                    existing[key] = {
                        'start': '' if hook.get('start') is None else str(hook.get('start', '')),
                        'end': '' if hook.get('end') is None else str(hook.get('end', '')),
                        'lrc_path': str(item.get('lrc_path', '') or ''),
                    }
            except Exception as exc:
                raise Phase3Error('HOOK_PLAN_INVALID', f'Cannot read existing {path.name}: {exc}') from exc

        packages = scan_packages(input_dir, recursive=False)
        songs = []
        missing_lrc = []
        for pkg in packages:
            if not pkg.lrc.exists():
                missing_lrc.append(str(pkg.lrc.relative_to(root)))
            old = existing.get(pkg.basename.lower(), {'start': '', 'end': '', 'lrc_path': ''})
            discovered_lrc = str(pkg.lrc.relative_to(root)).replace('\\', '/')
            preserved_lrc = old.get('lrc_path', '') or discovered_lrc
            songs.append({
                'song_path': str(pkg.mp3.relative_to(root)).replace('\\', '/'),
                'lrc_path': preserved_lrc,
                'hook': {
                    'start': old.get('start', ''),
                    'end': old.get('end', ''),
                },
            })

        data = {
            'schema_version': 2,
            'description': 'Authoritative manual Reel timelines. --fillhookjson scans songs/final and preserves existing hook times; fill blank hook.start and hook.end values before processing.',
            'songs': songs,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return {
            'path': str(path),
            'song_count': len(songs),
            'new_count': sum(1 for s in songs if not existing.get(Path(s['song_path']).stem.lower())),
            'preserved_count': sum(1 for s in songs if existing.get(Path(s['song_path']).stem.lower(), {}).get('start') not in (None, '')),
            'missing_lrc': missing_lrc,
        }

    @classmethod
    def load(cls, root: Path, path: Path | None = None) -> 'HookPlan':
        path = path or (root / DEFAULT_FILENAME)
        if not path.exists():
            raise Phase3Error('HOOK_PLAN_MISSING', f'Create {path.name} in the project home folder before processing.')
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise Phase3Error('HOOK_PLAN_INVALID', f'{path}: {exc}') from exc
        if not isinstance(raw, dict) or not isinstance(raw.get('songs'), list):
            raise Phase3Error('HOOK_PLAN_INVALID', 'hook_timeline.json must contain a top-level "songs" array.')
        entries=[]; unconfigured=[]; seen_paths=set(); seen_names=set()
        for idx, item in enumerate(raw['songs']):
            if not isinstance(item, dict):
                raise Phase3Error('HOOK_PLAN_INVALID', f'songs[{idx}] must be an object.')
            song_path_value=item.get('song_path')
            hook=item.get('hook') if isinstance(item.get('hook'), dict) else item
            if not song_path_value:
                raise Phase3Error('HOOK_PLAN_INVALID', f'songs[{idx}] is missing song_path.')
            if not isinstance(hook, dict):
                raise Phase3Error('HOOK_PLAN_INVALID', f'songs[{idx}] is missing hook timing.')
            src = cls._resolve(root, song_path_value)
            if src.suffix.lower()!='.mp3':
                raise Phase3Error('HOOK_PLAN_INVALID', f'song_path must point to an MP3: {song_path_value}')
            if not src.exists():
                raise Phase3Error('HOOK_PLAN_SONG_MISSING', f'Song path does not exist: {src}')
            default_lrc = src.with_suffix('.lrc')
            if item.get('lrc_path'):
                lrc_value = str(item['lrc_path'])
            elif default_lrc.is_relative_to(root):
                lrc_value = str(default_lrc.relative_to(root)).replace('\\', '/')
            else:
                lrc_value = str(default_lrc)
            lrc = cls._resolve(root, lrc_value)
            basename=src.stem
            key=str(src).lower()
            if key in seen_paths: raise Phase3Error('HOOK_PLAN_INVALID', f'Duplicate song_path: {song_path_value}')
            if basename.lower() in seen_names: raise Phase3Error('HOOK_PLAN_INVALID', f'Duplicate song basename: {basename}')
            seen_paths.add(key); seen_names.add(basename.lower())

            start_raw=hook.get('start'); end_raw=hook.get('end')
            if start_raw in (None, '') or end_raw in (None, ''):
                unconfigured.append({'song_path':str(song_path_value),'lrc_path':str(lrc_value),'reason':'fill hook.start and hook.end'})
                continue
            try:
                start=parse_timecode(str(start_raw)); end=parse_timecode(str(end_raw))
            except Exception as exc:
                raise Phase3Error('HOOK_PLAN_INVALID', f'Invalid timeline for {song_path_value}: {exc}') from exc
            if end <= start:
                raise Phase3Error('HOOK_PLAN_INVALID', f'Hook end must be after start for {song_path_value}.')
            duration=end-start
            entries.append(HookPlanEntry(src,basename,start,end,str(song_path_value),str(lrc_value)))
        if not entries and not unconfigured:
            raise Phase3Error('HOOK_PLAN_INVALID', 'hook_timeline.json contains no songs.')
        return cls(root.resolve(), path.resolve(), entries, raw, unconfigured)

    def validate_package_and_duration(self, entry: HookPlanEntry, audio_info: dict) -> SongPackage:
        if audio_info.get('duration_ms',0) <= 0:
            raise Phase3Error('HOOK_PLAN_INVALID', f'Could not determine duration for {entry.song_path}')
        if entry.end_ms > int(audio_info['duration_ms']):
            raise Phase3Error('HOOK_PLAN_INVALID', f'Hook {entry.source_song_path} ends at {entry.end_ms} ms but song is only {audio_info["duration_ms"]} ms long.')
        lrc=self._resolve(self.root, entry.source_lrc_path); js=entry.song_path.with_suffix('.json')
        if not lrc.exists():
            raise Phase3Error('HOOK_PLAN_LRC_MISSING', f'LRC path does not exist: {lrc}')
        return SongPackage(entry.basename,entry.song_path,lrc,js)

    def by_basename(self, basename: str) -> HookPlanEntry:
        for e in self.entries:
            if e.basename==basename: return e
        raise Phase3Error('HOOK_PLAN_NOT_FOUND', f'No hook timeline configured for {basename}.')
