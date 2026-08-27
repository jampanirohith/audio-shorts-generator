import json
import shutil
import subprocess
from pathlib import Path


def _require_command(name):
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} was not found on PATH.")


def probe(path):
    _require_command("ffprobe")
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode:
        raise RuntimeError(proc.stdout[-6000:] or "ffprobe failed.")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe returned invalid JSON.") from exc


def _ffmpeg_version():
    try:
        proc = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        return (proc.stdout or "").splitlines()[0] if proc.stdout else None
    except Exception:
        return None


def _nvenc_available():
    if shutil.which("ffmpeg") is None:
        return False
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode == 0 and "h264_nvenc" in proc.stdout


def render(video, start, end, output, cfg):
    _require_command("ffmpeg")

    width = int(cfg["video_width"])
    height = int(cfg["video_height"])
    if width <= 0 or height <= 0:
        raise ValueError("video_width and video_height must be positive integers.")

    crop_width = float(cfg.get("source_crop_width", 0.70))
    crop_height = float(cfg.get("source_crop_height", 0.55))
    if not (0 < crop_width <= 1 and 0 < crop_height <= 1):
        raise ValueError("source_crop_width/source_crop_height must be in (0, 1].")

    start = float(start)
    end = float(end)
    if start < 0 or end <= start:
        raise ValueError("Invalid hook start/end values.")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(output.stem + ".rendering.mp4")

    # The crop is applied first. The resulting crop is scaled to the COMPLETE
    # output width. Its height is preserved from the crop aspect ratio and it
    # is centered on the black output canvas. This deliberately upscales small
    # sources so they never become a tiny centered landscape box.
    cinematic = bool(cfg.get("cinematic_enabled", True))
    cinematic_filters = ""
    if cinematic:
        cinematic_filters = (
            f"eq="
            f"brightness={cfg.get('cinematic_brightness', 0.0)}:"
            f"contrast={cfg.get('cinematic_contrast', 1.10)}:"
            f"saturation={cfg.get('cinematic_saturation', 1.03)}:"
            f"gamma={cfg.get('cinematic_gamma', 1.02)},"
            f"unsharp=5:5:{cfg.get('cinematic_sharpen', 0.30)}:5:5:0,"
            f"vignette=PI/{cfg.get('cinematic_vignette_divisor', 7)}:eval=frame,"
        )

    filters = (
        f"[0:v]"
        f"crop=iw*{crop_width}:ih*{crop_height}:(iw-ow)/2:(ih-oh)/2,"
        f"scale={width}:-1:flags=lanczos,"
        f"setsar=1,"
        f"{cinematic_filters}"
        f"format=yuv420p"
        f"[foreground];"
        f"color=c=black:s={width}x{height}:r={cfg.get('video_fps', 30)}"
        f"[background];"
        f"[background][foreground]"
        f"overlay=(W-w)/2:(H-h)/2:shortest=1"
        f"[video]"
    )

    def encoder_args(use_gpu):
        if use_gpu:
            return [
                "-c:v", "h264_nvenc",
                "-preset", str(cfg.get("nvenc_preset", "p5")),
                "-cq", str(cfg.get("nvenc_cq", 20)),
                "-b:v", "0",
            ]
        return [
            "-c:v", "libx264",
            "-preset", str(cfg.get("cpu_preset", "medium")),
            "-crf", str(cfg.get("video_crf", 18)),
        ]

    encoder_mode = str(cfg.get("video_encoder", "auto")).lower()
    if encoder_mode not in {"auto", "gpu", "nvenc", "cpu", "x264"}:
        raise ValueError("video_encoder must be auto, gpu/nvenc, or cpu/x264.")

    wants_gpu = encoder_mode in {"auto", "gpu", "nvenc"}
    gpu_available = wants_gpu and _nvenc_available()

    print(
        f"Crop: {crop_width:.2f} x {crop_height:.2f} of source | "
        f"output canvas: {width}x{height}",
        flush=True,
    )
    print(
        f"Cropped source is scaled to {width}px width and centered on the canvas",
        flush=True,
    )

    def run_render(use_gpu):
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.3f}",
            "-i", str(video),
            "-t", f"{end - start:.3f}",
            "-filter_complex", filters,
            "-map", "[video]",
            "-map", "0:a?",
            "-r", str(cfg.get("video_fps", 30)),
            *encoder_args(use_gpu),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", str(cfg.get("audio_bitrate", "192k")),
            "-movflags", "+faststart",
            str(temporary_output),
        ]
        return command, subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    used_gpu = False
    command_used = None
    try:
        if gpu_available:
            print("Encoder: NVIDIA NVENC/GPU (auto-detected)", flush=True)
            command_used, proc = run_render(True)
            if proc.returncode == 0:
                used_gpu = True
            else:
                print(
                    "NVENC is exposed by FFmpeg but could not be initialized; "
                    "falling back to CPU x264.",
                    flush=True,
                )
                if temporary_output.exists():
                    temporary_output.unlink()
                command_used, proc = run_render(False)
        else:
            print("Encoder: CPU x264", flush=True)
            command_used, proc = run_render(False)

        if proc.returncode:
            raise RuntimeError(proc.stdout[-8000:] or "FFmpeg rendering failed.")

        if not temporary_output.is_file() or temporary_output.stat().st_size == 0:
            raise RuntimeError("FFmpeg reported success but produced no output file.")

        temporary_output.replace(output)
    finally:
        if temporary_output.exists():
            temporary_output.unlink(missing_ok=True)

    final_probe = probe(output)

    return {
        "ffmpeg_version": _ffmpeg_version(),
        "command_used": command_used,
        "canvas": {
            "width": width,
            "height": height,
            "fps": cfg.get("video_fps", 30),
            "aspect_ratio": f"{width}:{height}",
            "background": "pure black",
        },
        "source_crop": {
            "width_fraction": crop_width,
            "height_fraction": crop_height,
            "position": "center",
        },
        "cropped_video_scaling": {
            "target_width_pixels": width,
            "height_mode": "preserve cropped aspect ratio",
            "horizontal_position": "center",
            "vertical_position": "center",
            "small_sources_upscaled": True,
            "fit_mode": "width_locked",
        },
        "cinematic_adjustment": {
            "enabled": cinematic,
            "brightness": cfg.get("cinematic_brightness", 0.0),
            "contrast": cfg.get("cinematic_contrast", 1.10),
            "saturation": cfg.get("cinematic_saturation", 1.03),
            "gamma": cfg.get("cinematic_gamma", 1.02),
            "sharpen": cfg.get("cinematic_sharpen", 0.30),
            "vignette_divisor": cfg.get("cinematic_vignette_divisor", 7),
            "description": "subtle contrast/color separation, gamma lift, restrained sharpening and vignette",
        },
        "encoder": "h264_nvenc" if used_gpu else "libx264",
        "encoder_requested": encoder_mode,
        "nvenc_available": _nvenc_available() if wants_gpu else False,
        "audio": {
            "codec": "aac",
            "bitrate": cfg.get("audio_bitrate", "192k"),
        },
        "output_probe": final_probe,
    }
