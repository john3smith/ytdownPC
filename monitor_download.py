"""Resume one YTDownPC download and record its result without an AI polling loop."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ytdownpc import DEFAULT_OUTPUT, download_video, validate_media_url


VIDEO_URL = "https://www.youtube.com/watch?v=ijdb8G6kBhc"
VIDEO_ID = "ijdb8G6kBhc"
STATUS_FILE = Path(__file__).with_name(f"monitor-{VIDEO_ID}.json")
_last_write = 0.0


def save_status(status: str, **details: object) -> None:
    payload = {
        "video_id": VIDEO_ID,
        "url": VIDEO_URL,
        "status": status,
        "updated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        **details,
    }
    temporary = STATUS_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, STATUS_FILE)


def progress(event: dict[str, object]) -> None:
    global _last_write
    now = time.monotonic()
    if now - _last_write < 10:
        return
    _last_write = now
    save_status(
        "downloading",
        stage=event.get("stage"),
        downloaded_bytes=event.get("downloaded"),
        estimated_total_bytes=event.get("total"),
        percent=event.get("percent"),
        speed_bytes_per_second=event.get("speed"),
    )


def main() -> int:
    try:
        url = validate_media_url(VIDEO_URL)
        save_status("starting", output_dir=str(DEFAULT_OUTPUT))
        result = download_video(url, DEFAULT_OUTPUT, "best", progress)
        output = Path(result.get("file") or "")
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("YTDownPC did not produce a non-empty final file")
        save_status("completed", file=str(output), size_bytes=output.stat().st_size)
        return 0
    except Exception as exc:
        save_status("failed", error=str(exc))
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
