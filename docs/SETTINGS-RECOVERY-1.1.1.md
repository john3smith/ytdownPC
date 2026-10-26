# YTDownPC 1.1.1 settings recovery

Settings now accept only a bounded JSON object and known, correctly typed
options. Empty, invalid, deeply nested and oversized input falls back to the
defaults without replacing the original settings file. Runtime-library metadata
also rejects invalid object shapes, timestamps and SHA-256 values rather than
crashing startup or treating future timestamps as a completed update.

The offline feature/MCP suite passed 27 tests using temporary synthetic settings,
mock network responses and synthetic runtime archives. Download algorithms and
the user's existing settings, cookies and downloaded media were not changed.
An actual site download is outside this settings-only verification.

Source version 1.1.1 does not imply a newly signed Windows binary. The existing
[Windows signing gate](WINDOWS_SIGNING.md) still applies. A new executable may
be published only after its signing and product checks have passed.
