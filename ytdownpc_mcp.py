"""Local stdio MCP bridge for YTDownPC. No download starts on server launch."""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from ytdownpc import DEFAULT_OUTPUT, FORMAT_SELECTORS, download_video, probe_video, validate_media_url


server = MCPServer("ytdownpc")
_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


@server.tool()
def video_info(url: str) -> dict[str, Any]:
    """Read public video metadata without downloading it."""
    return probe_video(validate_media_url(url))


@server.tool()
def start_download(url: str, quality: str = "best") -> dict[str, str]:
    """Download one public video to the Windows Downloads folder. Returns a job ID."""
    url = validate_media_url(url)
    if quality not in FORMAT_SELECTORS:
        raise ValueError(f"quality must be one of: {', '.join(FORMAT_SELECTORS)}")

    job_id = uuid.uuid4().hex
    with _lock:
        if any(job["status"] in {"queued", "running"} for job in _jobs.values()):
            raise RuntimeError("A YTDownPC MCP download is already running")
        _jobs[job_id] = {
            "status": "queued",
            "url": url,
            "quality": quality,
            "output_dir": str(DEFAULT_OUTPUT),
            "progress": None,
            "result": None,
            "error": None,
        }

    def on_progress(event: dict[str, Any]) -> None:
        with _lock:
            if event.get("stage") == "downloading":
                _jobs[job_id]["progress"] = round(float(event.get("percent") or 0), 1)

    def worker() -> None:
        with _lock:
            _jobs[job_id]["status"] = "running"
        try:
            result = download_video(url, DEFAULT_OUTPUT, quality, on_progress)
            path = Path(result.get("file") or "")
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError("Download returned no non-empty output file")
            with _lock:
                _jobs[job_id].update(status="completed", progress=100, result=result)
        except Exception as exc:
            with _lock:
                _jobs[job_id].update(status="failed", error=str(exc))

    threading.Thread(target=worker, name=f"ytdownpc-{job_id[:8]}", daemon=True).start()
    return {"job_id": job_id, "status": "queued", "output_dir": str(DEFAULT_OUTPUT)}


@server.tool()
def download_status(job_id: str) -> dict[str, Any]:
    """Read the progress and result of a download started by this MCP server."""
    with _lock:
        if job_id not in _jobs:
            raise ValueError("Unknown job ID (jobs are lost when the MCP server restarts)")
        return {"job_id": job_id, **_jobs[job_id].copy()}


if __name__ == "__main__":
    server.run(transport="stdio")
