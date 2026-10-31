# Android feature comparison and Windows 1.2.0 validation

Compared against Android 1.9.34, commit `c6cfb5f`. Android source and releases were
read only. Windows starts from `0afc529b`, retaining existing settings recovery,
per-job options, queue capacity/FIFO, process-tree cancellation, Wi-Fi start gate,
original-photo extraction, M4A, account discovery and conservative partial cleanup.

## Added desktop behavior

| Android behavior | Windows adaptation |
| --- | --- |
| New supported video site / aliases | Valid Pornhub viewkey/embed links normalized to HTTPS; youtube-nocookie.com and instagr.am accepted with host boundaries |
| Receive links when returning to app | Foreground-only clipboard import, text link extraction, persisted immediate toggle, duplicate automatic-start suppression |
| Download-centered screen | Primary download action, collapsible options, scrollable small-window view; login/account actions in their own tab |
| Explicit page/session preparation | Successful trusted HTTPS page load, minimum 3 seconds, explicit session-use button; navigation invalidates readiness |
| Browser request context | App profile User-Agent and scoped cookies captured in the queued job; Windows DPAPI protects worker handoff |
| Streaming progress | yt-dlp's FFmpeg downloader; per-item progress file, elapsed time/duration capped at 99; unknown duration shows elapsed time/size |
| Detailed transport failures | Bounded, redacted worker stderr plus actionable TLS/401/403/404/reset/timeout/FFmpeg advice |
| Verify output before success | Image format or first second decode, stable file size/mtime, SHA-256; receipts available as result.artifacts |

Android-specific share intents, MediaStore publishing, notifications/wake locks
and the local Android TLS helper are represented by paste/drop, Windows folders,
tray/process queue and Windows HTTPS tooling. The Windows browser does not
implement Android's secure-window screenshot flag. These platform differences
are not claims of identical low-level behavior. No new runtime dependency or
asset was added; original dependency notices and replaceable Qt DLL layout remain.

## Validation on 2026-10-31

- Feature/MCP/desktop suite: 36 passing checks. Authenticode policy: 10 passing checks.
- Generated two-second video/audio, served only on loopback: actual yt-dlp video
  download, M4A conversion, FFmpeg HTTPS streaming with progress and exact-output
  re-request. The synthetic CA is supplied explicitly to the test only; no host
  certificate installation or TLS bypass. Invalid files/audio-only-as-video fail.
- Qt UI, synthetic settings/clipboard and fresh window: 940x800, 640x480, 1.3x
  text; expanded/collapsed options, audio/quality controls, every scrollable
  action reachable, duplicate automatic downloads suppressed, manual retry kept.
- Readiness rejects off-site/lookalike hosts and remains disabled until the
  trusted page finishes loading and the three seconds elapse.
- Current stable yt-dlp 2026.10.26 (verified by the existing updater): actual
  [Blender Sintel YouTube](https://www.youtube.com/watch?v=eRsGyueVLvQ) downloads:
  MP4 720p 55,231,352 bytes, SHA-256
  `88f03ac33cc6805f59f00ed2614ebcac37a3f94b4fd7aaa96d3ecd7fdbffaef0`;
  M4A 45,794,395 bytes, SHA-256
  `dbd796cd8467c589d1c1e01f1c836d9808ec25880b3c3e855ebfddcd74fece11`.
  Actual stream metadata and first second decoding checked, not all frames.
- The old youtube-dl test video `BaW_jenozKc` was unavailable; it was not counted
  as a successful download.
- An existing process-tree test had a file-exists/empty-PID write race. It now
  waits for nonempty content and reaps the process even on failure.

Actual Pornhub login/video, authenticated X/Instagram full-account enumeration,
and all possible website/network changes remain unverified. Tests use owned
synthetic video and the open Blender film; no website media, cookies, runtime
data, profiles, screenshots or logs are packaged or committed.

## Delivery boundary

Windows build candidate 1.2.0 is separate from a signed production release.
The [existing signing gate](WINDOWS_SIGNING.md) remains in place. No current-user
or machine code-signing certificate and no standard SDK SignTool were found in
the read-only checks. Publishing an unsigned candidate needs an explicit owner
decision; this feature request does not silently remove the gate.

## Primary implementation references

- [Qt application activation](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QGuiApplication.html)
- [Qt scroll area sizing](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QScrollArea.html)
- [yt-dlp FFmpeg downloader](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/downloader/external.py)
- [FFmpeg progress protocol](https://ffmpeg.org/ffmpeg-doc.html)
- [Blender's download/watch page](https://durian.blender.org/download/)
