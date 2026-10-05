#!/usr/bin/env python3
"""Windows GUI and CLI for downloading public videos with yt-dlp."""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable
from urllib.parse import urlparse

import imageio_ffmpeg
import yt_dlp

from version_info import APP_NAME, APP_VERSION


APP_DIR = Path(__file__).resolve().parent
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"
DEFAULT_OUTPUT = Path.home() / "Downloads"
QUALITY_LABELS = {
    "최고 화질": "best",
    "1080p 이하": "1080",
    "720p 이하": "720",
}
FORMAT_SELECTORS = {
    "best": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
    "1080": (
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/"
        "b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b[height<=1080]"
    ),
    "720": (
        "bv*[height<=720][ext=mp4]+ba[ext=m4a]/"
        "b[height<=720][ext=mp4]/bv*[height<=720]+ba/b[height<=720]"
    ),
}


def validate_media_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    valid_hosts = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "instagram.com",
        "www.instagram.com",
        "m.instagram.com",
        "x.com",
        "www.x.com",
        "mobile.x.com",
        "twitter.com",
        "www.twitter.com",
        "mobile.twitter.com",
        "t.co",
    }
    if parsed.scheme not in {"http", "https"} or host not in valid_hosts:
        raise ValueError(
            "YouTube, Instagram 또는 X/Twitter 영상 주소를 입력해 주세요."
        )
    return url


def format_bytes(value: float | int | None) -> str:
    if not value:
        return "0 B"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def find_downloaded_file(output_dir: Path, video_id: str) -> Path | None:
    candidates = [
        path
        for path in output_dir.iterdir()
        if path.is_file()
        and f"[{video_id}]" in path.name
        and path.suffix.lower() not in {".part", ".ytdl"}
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


class YdlLogger:
    def __init__(self, callback: Callable[[str], None]) -> None:
        self.callback = callback

    def debug(self, message: str) -> None:
        if not message.startswith("[debug]"):
            logging.debug(message)

    def info(self, message: str) -> None:
        logging.info(message)

    def warning(self, message: str) -> None:
        logging.warning(message)
        self.callback(message)

    def error(self, message: str) -> None:
        logging.error(message)
        self.callback(message)


def download_video(
    url: str,
    output_dir: Path,
    quality: str = "best",
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    url = validate_media_url(url)
    if quality not in FORMAT_SELECTORS:
        raise ValueError(f"지원하지 않는 화질입니다: {quality}")

    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = output_dir / ".parts"
    temp_dir.mkdir(parents=True, exist_ok=True)

    def emit(event: dict[str, Any]) -> None:
        if progress:
            progress(event)

    def progress_hook(data: dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            downloaded = int(data.get("downloaded_bytes") or 0)
            total = int(
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
                or 0
            )
            percent = (downloaded / total * 100) if total else 0
            emit(
                {
                    "stage": "downloading",
                    "percent": percent,
                    "downloaded": downloaded,
                    "total": total,
                    "speed": data.get("speed"),
                    "eta": data.get("eta"),
                }
            )
        elif status == "finished":
            emit({"stage": "processing", "percent": 100})

    options: dict[str, Any] = {
        "format": FORMAT_SELECTORS[quality],
        "paths": {"home": str(output_dir), "temp": str(temp_dir)},
        "outtmpl": {"default": "%(title).180B [%(id)s].%(ext)s"},
        "merge_output_format": "mp4",
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "windowsfilenames": True,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        "logger": YdlLogger(lambda message: emit({"stage": "message", "text": message})),
    }

    emit({"stage": "preparing", "percent": 0})
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)

    video_id = str(info.get("id") or "")
    downloaded_file = find_downloaded_file(output_dir, video_id)
    result = {
        "id": video_id,
        "title": str(info.get("title") or ""),
        "channel": str(info.get("channel") or info.get("uploader") or ""),
        "file": str(downloaded_file) if downloaded_file else "",
    }
    emit({"stage": "complete", "percent": 100, **result})
    return result


def probe_video(url: str) -> dict[str, Any]:
    url = validate_media_url(url)
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "live_status": info.get("live_status"),
    }


class DownloaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.running = False

        root.title(APP_TITLE)
        root.geometry("680x430")
        root.minsize(620, 390)
        root.configure(bg="#f4f6f8")
        root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f6f8")
        style.configure("TLabel", background="#f4f6f8", foreground="#202124")
        style.configure("Title.TLabel", font=("Malgun Gothic", 18, "bold"))
        style.configure("Field.TLabel", font=("Malgun Gothic", 10, "bold"))
        style.configure("TButton", font=("Malgun Gothic", 10), padding=(12, 8))
        style.configure("Primary.TButton", font=("Malgun Gothic", 10, "bold"))
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#dde2e7",
            background="#1677ff",
            bordercolor="#dde2e7",
        )

        outer = ttk.Frame(root, padding=24)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_TITLE, style="Title.TLabel").pack(
            anchor="w", pady=(0, 22)
        )

        ttk.Label(
            outer,
            text="YouTube · Instagram · X/Twitter 영상 주소",
            style="Field.TLabel",
        ).pack(anchor="w")
        url_row = ttk.Frame(outer)
        url_row.pack(fill="x", pady=(7, 18))
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_row, textvariable=self.url_var, font=("Malgun Gothic", 10))
        self.url_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(url_row, text="붙여넣기", command=self.paste_url).pack(
            side="left", padx=(8, 0)
        )

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 18))

        quality_box = ttk.Frame(controls)
        quality_box.pack(side="left", fill="x", expand=True)
        ttk.Label(quality_box, text="화질", style="Field.TLabel").pack(anchor="w")
        self.quality_var = tk.StringVar(value="최고 화질")
        quality = ttk.Combobox(
            quality_box,
            textvariable=self.quality_var,
            values=list(QUALITY_LABELS),
            state="readonly",
            width=18,
        )
        quality.pack(anchor="w", pady=(7, 0))

        folder_box = ttk.Frame(controls)
        folder_box.pack(side="left", fill="x", expand=True, padx=(20, 0))
        ttk.Label(folder_box, text="저장 위치", style="Field.TLabel").pack(anchor="w")
        folder_row = ttk.Frame(folder_box)
        folder_row.pack(fill="x", pady=(7, 0))
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
        ttk.Entry(folder_row, textvariable=self.output_var).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(folder_row, text="선택", command=self.choose_folder).pack(
            side="left", padx=(8, 0)
        )

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            outer, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill="x", pady=(3, 8))

        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", side="bottom", pady=(22, 0))
        ttk.Button(actions, text="폴더 열기", command=self.open_folder).pack(side="left")
        self.download_button = ttk.Button(
            actions,
            text="다운로드",
            command=self.start_download,
            style="Primary.TButton",
        )
        self.download_button.pack(side="right")

        self.url_entry.focus_set()
        root.after(150, self.process_events)

    def paste_url(self) -> None:
        try:
            self.url_var.set(self.root.clipboard_get().strip())
        except tk.TclError:
            messagebox.showinfo("클립보드", "클립보드에 텍스트가 없습니다.")

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_var.get())
        if selected:
            self.output_var.set(selected)

    def open_folder(self) -> None:
        folder = Path(self.output_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def start_download(self) -> None:
        if self.running:
            return
        try:
            url = validate_media_url(self.url_var.get())
            output = Path(self.output_var.get()).expanduser().resolve()
        except (ValueError, OSError) as exc:
            messagebox.showerror("입력 오류", str(exc))
            return

        self.running = True
        self.download_button.configure(state="disabled")
        self.progress_var.set(0)
        self.status_var.set("영상 정보를 확인하는 중")
        quality = QUALITY_LABELS[self.quality_var.get()]
        threading.Thread(
            target=self.download_worker,
            args=(url, output, quality),
            name="download-worker",
            daemon=True,
        ).start()

    def download_worker(self, url: str, output: Path, quality: str) -> None:
        try:
            result = download_video(url, output, quality, self.events.put)
            self.events.put({"stage": "worker-complete", "result": result})
        except Exception as exc:
            logging.exception("download failed")
            self.events.put({"stage": "error", "text": str(exc)})

    def process_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            self.apply_event(event)
        self.root.after(150, self.process_events)

    def apply_event(self, event: dict[str, Any]) -> None:
        stage = event.get("stage")
        if stage == "downloading":
            percent = float(event.get("percent") or 0)
            self.progress_var.set(percent)
            speed = format_bytes(event.get("speed")) + "/s" if event.get("speed") else ""
            eta = f" · 남은 시간 {event.get('eta')}초" if event.get("eta") is not None else ""
            self.status_var.set(f"다운로드 중 {percent:.1f}% · {speed}{eta}".strip(" ·"))
        elif stage == "processing":
            self.progress_var.set(100)
            self.status_var.set("영상과 음성을 합치는 중")
        elif stage == "message" and event.get("text"):
            self.status_var.set(str(event["text"])[:120])
        elif stage == "worker-complete":
            self.running = False
            self.download_button.configure(state="normal")
            self.progress_var.set(100)
            result = event.get("result") or {}
            self.status_var.set(f"완료: {result.get('title') or '영상'}")
            messagebox.showinfo("다운로드 완료", result.get("file") or "다운로드가 완료됐습니다.")
        elif stage == "error":
            self.running = False
            self.download_button.configure(state="normal")
            self.status_var.set("다운로드 실패")
            messagebox.showerror("다운로드 실패", str(event.get("text") or "알 수 없는 오류"))

    def close(self) -> None:
        if self.running and not messagebox.askyesno(
            "종료 확인", "다운로드가 진행 중입니다. 프로그램을 종료할까요?"
        ):
            return
        self.root.destroy()


def configure_file_logging(path: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")

    parser = argparse.ArgumentParser(
        description="Download public videos from YouTube, Instagram, and X/Twitter."
    )
    parser.add_argument("--url")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--quality", choices=sorted(FORMAT_SELECTORS), default="best")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--log-file", type=Path)
    args = parser.parse_args()

    configure_file_logging(args.log_file)
    if args.probe:
        if not args.url:
            parser.error("--probe requires --url")
        print(json.dumps(probe_video(args.url), ensure_ascii=False))
        return 0
    if args.url:
        result = download_video(
            args.url,
            args.output,
            args.quality,
            lambda event: logging.info("progress %s", event),
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
