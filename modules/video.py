import subprocess, re
from pathlib import Path


def lrc(path):
    out = []
    if not path or not Path(path).exists():
        return out
    for line in Path(path).read_text(encoding='utf-8-sig', errors='ignore').splitlines():
        ts = re.findall(r'\[(\d+):([0-9]+(?:\.[0-9]+)?)\]', line)
        text = re.sub(r'\[[^\]]+\]', '', line).strip()
        for m, s in ts:
            if text:
                out.append((int(m) * 60 + float(s), text))
    return sorted(out)


def ass_time(t):
    t = max(0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


def _font_name(cfg):
    candidates = [
        cfg.get('telugu_font_path', ''),
        str(Path('fonts') / 'NotoSerifTelugu-Medium.ttf'),
        str(Path('fonts') / 'NotoSerifTelugu-Regular.ttf'),
        r'C:\Windows\Fonts\NotoSerifTelugu-Regular.ttf',
        r'C:\Windows\Fonts\NirmalaUI.ttf',
    ]
    for p in candidates:
        if p and Path(p).exists():
            if 'Gurajada' in p:
                return 'Noto Serif Telugu'
            if 'Noto' in p:
                return 'Noto Serif Telugu'
            return 'Nirmala UI'
    return cfg.get('telugu_font', 'Noto Serif Telugu')


def make_ass(lrc_file, start, end, alignment, out, cfg):
    lines = lrc(lrc_file)
    rows = []
    offset = float(alignment.get('spotify_to_youtube_offset_seconds', 0))
    scale = float(alignment.get('time_scale', 1.0))
    for i, (t, text) in enumerate(lines):
        yt = t * scale + offset
        if yt < start or yt > end or not text:
            continue
        nxt = end
        for tt, _ in lines[i + 1:]:
            yy = tt * scale + offset
            if yy > yt:
                nxt = min(end, yy)
                break
        # Centered cinematic Telugu typography. ASS italic gives the serif face a
        # handwritten/italic poster look similar in spirit to Gurajada Italic.
        rows.append(
            f'Dialogue: 0,{ass_time(yt-start)},{ass_time(nxt-start)},Telugu,,0,0,0,,{{\\fad(120,120)}}{text}'
        )

    font = _font_name(cfg)
    header = f'''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Telugu,{font},{cfg['subtitle_font_size']},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,0,1,0,0,100,100,0,0,1,{cfg['subtitle_outline']},2,5,70,70,{cfg['subtitle_margin_v']},1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    Path(out).write_text(header + '\n'.join(rows), encoding='utf-8')
    return bool(rows)


def _escape_filter_path(p):
    s = str(Path(p).resolve()).replace('\\', '/')
    return s.replace(':', '\\:').replace("'", "\\'")


def _has_nvenc():
    try:
        p = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        return 'h264_nvenc' in p.stdout
    except Exception:
        return False


def _encoder_args(cfg):
    mode = str(cfg.get('video_encoder', 'auto')).lower()
    use_gpu = mode in ('auto', 'nvenc', 'gpu') and _has_nvenc()
    if use_gpu:
        return ['-c:v', 'h264_nvenc', '-preset', cfg.get('nvenc_preset', 'p5'),
                '-cq', str(cfg.get('nvenc_cq', 20)), '-b:v', '0'], 'NVIDIA NVENC'
    return ['-c:v', 'libx264', '-preset', cfg.get('cpu_preset', 'medium'),
            '-crf', str(cfg.get('video_crf', 18))], 'CPU x264'


def render(video, start, end, ass, out, cfg, preview=False):
    """Render a 1080x1920 reel.

    The portrait canvas is pure black. The source remains landscape and is centered.
    A small configurable CENTER crop removes edge black bars/watermarks, but the
    landscape image is never cropped to portrait and is never stretched.
    """
    w, h = int(cfg['video_width']), int(cfg['video_height'])
    fg_w = min(int(cfg.get('foreground_width', 1080)), w)
    fps = int(cfg.get('video_fps', 30))
    cw = float(cfg.get('source_crop_width', 0.96))
    ch = float(cfg.get('source_crop_height', 0.92))
    cw = min(max(cw, 0.80), 1.0)
    ch = min(max(ch, 0.80), 1.0)

    # Crop a small amount from the source edges, then fit the resulting landscape
    # frame inside 1080px width. The surrounding portrait area is literally black.
    crop_w = f'iw*{cw:.4f}'
    crop_h = f'ih*{ch:.4f}'
    filt = (
        f'[0:v]crop={crop_w}:{crop_h}:(iw-ow)/2:(ih-oh)/2,'
        f'scale={fg_w}:-2:flags=lanczos,setsar=1,'
        f'eq=brightness={cfg["cinematic_brightness"]}:contrast={cfg["cinematic_contrast"]}:saturation={cfg["cinematic_saturation"]}[fg];'
        f'color=c=black:s={w}x{h}:r={fps}[bg];'
        f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v]'
    )
    if ass:
        filt += f";[v]subtitles=filename='{_escape_filter_path(ass)}':fontsdir='{_escape_filter_path(Path('fonts'))}'[vout]"
        mapv = '[vout]'
    else:
        mapv = '[v]'

    enc, enc_name = _encoder_args(cfg)
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-ss', str(start), '-i', str(video), '-t', str(end-start),
        '-filter_complex', filt, '-map', mapv, '-map', '0:a?',
        '-r', str(fps), *enc,
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart', str(out)
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       encoding='utf-8', errors='replace')
    if p.returncode:
        # If NVENC is selected but fails (driver/build issue), retry once with CPU x264.
        if enc_name == 'NVIDIA NVENC':
            cpu = ['-c:v', 'libx264', '-preset', cfg.get('cpu_preset', 'medium'),
                   '-crf', str(cfg.get('video_crf', 18))]
            cmd2 = [x for x in cmd]
            # Replace the encoder section by reconstructing the tail safely.
            idx = cmd2.index('-c:v')
            del cmd2[idx:idx+6]
            cmd2[idx:idx] = cpu
            p2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding='utf-8', errors='replace')
            if p2.returncode == 0:
                return
            raise RuntimeError(p2.stdout[-8000:])
        raise RuntimeError(p.stdout[-8000:])


def preview(video, hook, out, cfg):
    render(video, hook['start'], hook['end'], None, out, cfg, preview=True)
