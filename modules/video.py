import subprocess
from pathlib import Path


def _nvenc():
    try:
        return "h264_nvenc" in subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        ).stdout
    except Exception:
        return False


def render(video, start, end, out, cfg):
    w, h = int(cfg["video_width"]), int(cfg["video_height"])
    cw = float(cfg.get("source_crop_width", 0.70))
    ch = float(cfg.get("source_crop_height", 0.55))

    # Crop first, then ALWAYS scale the cropped result to the full reel width.
    # Height follows the crop's aspect ratio. The resulting video is vertically
    # centered on a pure-black 1080x1920 canvas. This intentionally upscales
    # small source videos so they do not appear as a tiny strip.
    filt = (
        f"[0:v]crop=iw*{cw}:ih*{ch}:(iw-ow)/2:(ih-oh)/2,"
        f"scale={w}:-1:flags=lanczos,"
        f"setsar=1,"
        f"eq=brightness={cfg.get('cinematic_brightness', .025)}:"
        f"contrast={cfg.get('cinematic_contrast', 1.08)}:"
        f"saturation={cfg.get('cinematic_saturation', 1.04)}[fg];"
        f"color=c=black:s={w}x{h}:r={cfg.get('video_fps', 30)}[bg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[v]"
    )

    gpu = str(cfg.get("video_encoder", "auto")).lower() in ("auto", "gpu", "nvenc") and _nvenc()
    enc = (
        ["-c:v", "h264_nvenc", "-preset", cfg.get("nvenc_preset", "p5"),
         "-cq", str(cfg.get("nvenc_cq", 20)), "-b:v", "0"]
        if gpu else
        ["-c:v", "libx264", "-preset", cfg.get("cpu_preset", "medium"),
         "-crf", str(cfg.get("video_crf", 18))]
    )

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(start), "-i", str(video), "-t", str(end - start),
        "-filter_complex", filt, "-map", "[v]", "-map", "0:a?",
        "-r", str(cfg.get("video_fps", 30)),
        *enc, "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(out),
    ]

    print(f"Crop: {cw:.2f} x {ch:.2f} of source", flush=True)
    print(f"Final canvas: {w}x{h} | cropped video stretched to {w}px width and vertically centered", flush=True)
    print(f"Encoder: {'NVIDIA NVENC/GPU' if gpu else 'CPU x264'}", flush=True)

    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError(p.stdout[-8000:])

    # Return render facts for the permanent JSON handoff.
    return {
        "canvas": {"width": w, "height": h, "fps": cfg.get("video_fps", 30), "background": "pure black"},
        "source_crop": {
            "width_fraction": cw,
            "height_fraction": ch,
            "position": "center",
        },
        "cropped_video_scaling": {
            "target_width_pixels": w,
            "height_mode": "preserve crop aspect ratio",
            "vertical_position": "center",
            "small_sources_upscaled": True,
        },
        "cinematic_adjustment": {
            "brightness": cfg.get("cinematic_brightness", .025),
            "contrast": cfg.get("cinematic_contrast", 1.08),
            "saturation": cfg.get("cinematic_saturation", 1.04),
        },
        "encoder": "h264_nvenc" if gpu else "libx264",
        "audio": {"codec": "aac", "bitrate": "192k"},
    }
