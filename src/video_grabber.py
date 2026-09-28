from __future__ import annotations
import json
from pathlib import Path
from .utils import Phase3Error, run_cmd, ffmpeg_has_encoder, nvenc_video_args
from .audio_io import probe


class VideoGrabber:
    def __init__(self, cfg, work_dir, logger):
        self.cfg = cfg
        self.work = work_dir
        self.logger = logger

    def _section_request(self, video_id: str, start_ms: int, end_ms: int) -> dict:
        guard_b = int(self.cfg.get('video_match.guard_before_ms', 1500))
        guard_a = int(self.cfg.get('video_match.guard_after_ms', 1500))
        start_ms = max(0, int(start_ms) - guard_b)
        end_ms = int(end_ms) + guard_a
        return {
            'video_id': str(video_id),
            'requested_start_ms': int(start_ms),
            'requested_end_ms': int(end_ms),
            'guard_before_ms': guard_b,
            'guard_after_ms': guard_a,
        }

    def download_section(self, video_id, start_ms, end_ms) -> Path:
        outdir = self.work / 'video'
        outdir.mkdir(parents=True, exist_ok=True)
        out = outdir / 'downloaded_with_guard.mp4'
        meta_path = outdir / 'downloaded_with_guard.request.json'
        request = self._section_request(video_id, start_ms, end_ms)
        expected_span_ms = request['requested_end_ms'] - request['requested_start_ms']

        # Never blindly reuse a stale section from a previous hook/timeline.
        reusable = False
        if out.exists() and out.stat().st_size > 10000 and meta_path.exists():
            try:
                cached = json.loads(meta_path.read_text(encoding='utf-8'))
                reusable = cached == request
                if reusable:
                    info = probe(out)
                    reusable = info.get('duration_ms', 0) >= max(0, expected_span_ms - 750)
            except Exception:
                reusable = False
        if reusable:
            if self.logger:
                self.logger.info('VideoGrabber: reusing matching cached section %.3fs', expected_span_ms / 1000.0)
            return out

        out.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        url = f'https://www.youtube.com/watch?v={video_id}'
        yt = self.cfg.get('video.yt_dlp_binary', 'yt-dlp')
        section = f"*{request['requested_start_ms']/1000:.3f}-{request['requested_end_ms']/1000:.3f}"
        try:
            run_cmd([
                yt, '--no-playlist',
                '-f', self.cfg.get('video.video_format'),
                '--download-sections', section,
                '--force-keyframes-at-cuts',
                '--merge-output-format', 'mp4',
                '-o', str(out), url,
            ], timeout=float(self.cfg.get('video.download_timeout_seconds', 600)))
        except Exception as e:
            raise Phase3Error('VIDEO_SECTION_DOWNLOAD_FAILED', str(e))
        if not out.exists():
            raise Phase3Error('VIDEO_SECTION_DOWNLOAD_FAILED', 'Segment file missing')

        try:
            info = probe(out)
        except Exception as exc:
            raise Phase3Error('VIDEO_SECTION_DOWNLOAD_FAILED', f'Could not probe downloaded section: {exc}') from exc
        actual_ms = int(info.get('duration_ms', 0))
        if actual_ms < max(1000, expected_span_ms - 1000):
            out.unlink(missing_ok=True)
            raise Phase3Error(
                'VIDEO_SECTION_DOWNLOAD_FAILED',
                f'Downloaded section is too short: expected about {expected_span_ms} ms, got {actual_ms} ms',
                details={'video_id': video_id, **request, 'actual_duration_ms': actual_ms},
            )
        meta_path.write_text(json.dumps(request, indent=2) + '\n', encoding='utf-8')
        if self.logger:
            self.logger.info('VideoGrabber: downloaded section %.3fs (actual %.3fs)', expected_span_ms / 1000.0, actual_ms / 1000.0)
        return out

    def _encode_trim(self, src: Path, dst: Path, duration_ms: int, codec: str, trim_start_ms: int = 0) -> None:
        duration_s = duration_ms / 1000.0
        if codec == 'h264_nvenc':
            codec_args = nvenc_video_args(self.cfg)
        else:
            codec_args = ['-c:v', 'libx264', '-preset', str(self.cfg.get('render.preset', 'fast')), '-crf', str(self.cfg.get('render.crf', 18)), '-pix_fmt', 'yuv420p']
        run_cmd([
            'ffmpeg', '-y', '-v', 'error',
            '-ss', f'{trim_start_ms / 1000.0:.6f}',
            '-i', str(src),
            '-map', '0:v:0',
            '-an',
            '-t', f'{duration_s:.6f}',
            *codec_args,
            '-movflags', '+faststart',
            str(dst),
        ], timeout=1800)

    def trim_exact(self, src: Path, dst: Path, duration_ms: int, trim_start_ms: int = 0):
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.unlink(missing_ok=True)
        if duration_ms <= 0:
            raise Phase3Error('VIDEO_TRIM_FAILED', f'Invalid requested duration: {duration_ms} ms')
        if trim_start_ms < 0:
            trim_start_ms = 0

        source_info = probe(src)
        available_after_trim_ms = max(0, int(source_info.get('duration_ms', 0)) - int(trim_start_ms))
        source_ms = int(source_info.get('duration_ms', 0))
        if available_after_trim_ms < duration_ms - 500:
            raise Phase3Error(
                'VIDEO_TRIM_FAILED',
                f'Source segment is too short after trim start: requested {duration_ms} ms, available {available_after_trim_ms} ms',
                details={'requested_duration_ms': int(duration_ms), 'trim_start_ms': int(trim_start_ms), 'source_duration_ms': source_ms, 'available_after_trim_ms': available_after_trim_ms, 'source': str(src)},
            )

        # Re-encode instead of stream-copying. Section downloads are frequently
        # keyframe-aligned, and stream copy can silently shorten the requested
        # interval. Re-encoding gives a stable exact-duration video segment.
        preferred = self.cfg.get('render.video_codec', 'h264_nvenc')
        if preferred == 'h264_nvenc' and ffmpeg_has_encoder('h264_nvenc'):
            try:
                self._encode_trim(src, dst, duration_ms, 'h264_nvenc', trim_start_ms)
            except Exception:
                dst.unlink(missing_ok=True)
                self._encode_trim(src, dst, duration_ms, 'libx264', trim_start_ms)
        else:
            self._encode_trim(src, dst, duration_ms, 'libx264', trim_start_ms)

        info = probe(dst)
        actual_ms = int(info.get('duration_ms', 0))
        if abs(actual_ms - duration_ms) > 250:
            raise Phase3Error(
                'VIDEO_TRIM_FAILED',
                f'Expected {duration_ms}, got {actual_ms}',
                details={'expected_duration_ms': int(duration_ms), 'actual_duration_ms': actual_ms, 'source_duration_ms': source_ms},
            )
