"""Ses & Video dönüştürücüleri; tamamı ffmpeg'i subprocess ile çağırır."""

import subprocess
from pathlib import Path

from . import options
from .base import register
from .tooling import FFMPEG, require_tool


def _run_ffmpeg(args: list[str], dst: Path) -> None:
    ffmpeg = require_tool(FFMPEG)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Kırpma: -ss/-to girdiden önce gelirse ffmpeg hızlı arama yapar (args[0] == '-i').
    trim: list[str] = []
    if options.get("trim_start"):
        trim += ["-ss", str(options.get("trim_start"))]
    if options.get("trim_end"):
        trim += ["-to", str(options.get("trim_end"))]

    # Ses bit hızı: çıktı dosyası (son eleman) öncesine eklenir.
    bitrate = options.get("audio_bitrate")
    if bitrate:
        args = args[:-1] + ["-b:a", str(bitrate)] + args[-1:]

    subprocess.run([ffmpeg, "-y", *trim, *args], check=True, capture_output=True)


@register(".mp4", ".mp3", "MP3 ses (videodan ses ayıklama)", requires=FFMPEG)
def mp4_to_mp3(src: Path, dst: Path) -> None:
    _run_ffmpeg(["-i", str(src), "-vn", "-acodec", "libmp3lame", "-q:a", "2", str(dst)], dst)


@register(".wav", ".mp3", "MP3 ses (sıkıştırılmış)", requires=FFMPEG)
def wav_to_mp3(src: Path, dst: Path) -> None:
    _run_ffmpeg(["-i", str(src), "-acodec", "libmp3lame", "-q:a", "2", str(dst)], dst)


@register(".mp3", ".wav", "WAV ses (kayıpsız)", requires=FFMPEG)
def mp3_to_wav(src: Path, dst: Path) -> None:
    _run_ffmpeg(["-i", str(src), str(dst)], dst)


def _audio_to_mp3(src: Path, dst: Path) -> None:
    _run_ffmpeg(["-i", str(src), "-acodec", "libmp3lame", "-q:a", "2", str(dst)], dst)


def _audio_to_wav(src: Path, dst: Path) -> None:
    _run_ffmpeg(["-i", str(src), str(dst)], dst)


@register(".m4a", ".mp3", "MP3 ses", requires=FFMPEG)
def m4a_to_mp3(src: Path, dst: Path) -> None:
    _audio_to_mp3(src, dst)


@register(".m4a", ".wav", "WAV ses (kayıpsız)", requires=FFMPEG)
def m4a_to_wav(src: Path, dst: Path) -> None:
    _audio_to_wav(src, dst)


@register(".flac", ".mp3", "MP3 ses (sıkıştırılmış)", requires=FFMPEG)
def flac_to_mp3(src: Path, dst: Path) -> None:
    _audio_to_mp3(src, dst)


@register(".flac", ".wav", "WAV ses (kayıpsız)", requires=FFMPEG)
def flac_to_wav(src: Path, dst: Path) -> None:
    _audio_to_wav(src, dst)


@register(".ogg", ".mp3", "MP3 ses", requires=FFMPEG)
def ogg_to_mp3(src: Path, dst: Path) -> None:
    _audio_to_mp3(src, dst)


@register(".ogg", ".wav", "WAV ses (kayıpsız)", requires=FFMPEG)
def ogg_to_wav(src: Path, dst: Path) -> None:
    _audio_to_wav(src, dst)


def _video_to_mp4(src: Path, dst: Path) -> None:
    # libx264 tek sayılı boyut kabul etmediği için her iki durumda da çifte yuvarlanır.
    height = options.get("video_height")
    scale = f"scale=-2:{height}" if height else "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    _run_ffmpeg(
        [
            "-i", str(src),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "faststart",
            "-pix_fmt", "yuv420p",
            "-vf", scale,
            str(dst),
        ],
        dst,
    )


@register(".mov", ".mp4", "MP4 video (uyumlu format)", requires=FFMPEG)
def mov_to_mp4(src: Path, dst: Path) -> None:
    _video_to_mp4(src, dst)


@register(".mkv", ".mp4", "MP4 video (uyumlu format)", requires=FFMPEG)
def mkv_to_mp4(src: Path, dst: Path) -> None:
    _video_to_mp4(src, dst)


@register(".webm", ".mp4", "MP4 video (uyumlu format)", requires=FFMPEG)
def webm_to_mp4(src: Path, dst: Path) -> None:
    _video_to_mp4(src, dst)


@register(".avi", ".mp4", "MP4 video (uyumlu format)", requires=FFMPEG)
def avi_to_mp4(src: Path, dst: Path) -> None:
    _video_to_mp4(src, dst)


@register(".mp4", ".webm", "WEBM video (web optimizasyonu)", requires=FFMPEG)
def mp4_to_webm(src: Path, dst: Path) -> None:
    _run_ffmpeg(
        ["-i", str(src), "-c:v", "libvpx-vp9", "-crf", "33", "-b:v", "0", "-c:a", "libopus", str(dst)],
        dst,
    )


@register(".mp4", ".wav", "WAV ses (videodan ses ayıklama)", requires=FFMPEG)
def mp4_to_wav(src: Path, dst: Path) -> None:
    _run_ffmpeg(["-i", str(src), "-vn", str(dst)], dst)


@register(".mov", ".mp3", "MP3 ses (videodan ses ayıklama)", requires=FFMPEG)
def mov_to_mp3(src: Path, dst: Path) -> None:
    _run_ffmpeg(["-i", str(src), "-vn", "-acodec", "libmp3lame", "-q:a", "2", str(dst)], dst)


@register(".gif", ".mp4", "MP4 video", requires=FFMPEG)
def gif_to_mp4(src: Path, dst: Path) -> None:
    _run_ffmpeg(
        [
            "-i", str(src),
            "-movflags", "faststart",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            str(dst),
        ],
        dst,
    )


@register(".mp4", ".gif", "GIF animasyon", requires=FFMPEG)
def mp4_to_gif(src: Path, dst: Path) -> None:
    _run_ffmpeg(
        ["-i", str(src), "-vf", "fps=10,scale=480:-1:flags=lanczos", str(dst)],
        dst,
    )