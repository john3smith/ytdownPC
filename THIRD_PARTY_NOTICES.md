# Third-party components

The portable distribution contains unmodified dynamically loaded Qt/PySide6
libraries, Chromium/QtWebEngine, Python, yt-dlp, yt-dlp-ejs, Node.js, Pillow,
curl-cffi and supporting packages. Their licenses remain separate from this
application. Package license texts and version inventory are in `docs/third-party`.
Qt's additional Chromium notices are available in the browser's `chrome://credits`
implementation and the QtWebEngine source tree; the external viewer intentionally
does not allow navigation to internal schemes.

Qt/PySide6 is distributed as separate DLL/PYD files in `_internal`, rather than a
single sealed executable. Replacement of compatible library files and debugging
modifications to those libraries is not prohibited by this application.
Sources and matching tags can be obtained from:

- https://code.qt.io/cgit/pyside/pyside-setup.git/ (v6.12.0)
- https://code.qt.io/cgit/qt/qtwebengine.git/ (v6.12.0)
- https://code.qt.io/cgit/qt/qtbase.git/ (v6.12.0)
- https://github.com/yt-dlp/yt-dlp (2026.08.19)
- https://github.com/yt-dlp/ejs (0.8.0)
- https://nodejs.org/dist/v24.19.0/ (source tarball, headers and license)
- https://github.com/lexiforest/curl_cffi (0.16.3)
- https://github.com/python-pillow/Pillow (13.0.0)

The installer/portable ZIP does **not** redistribute FFmpeg. When an existing
FFmpeg installation is unavailable, the app downloads the original upstream
imageio-ffmpeg 0.6.0 Windows wheel from PyPI, verifies its published SHA-256 and
extracts the binary on the user's machine. Source/provenance is recorded locally.
Upstream binary build information and corresponding source instructions:
https://github.com/imageio/imageio-ffmpeg and https://github.com/imageio/imageio-binaries.

Automatic yt-dlp updates come from the upstream stable GitHub Release and are
checked against the same Release's SHA-256 list. No authenticated browser data,
downloaded media, logs, user settings or cached runtime updates are included in
this distribution or Git repository.
