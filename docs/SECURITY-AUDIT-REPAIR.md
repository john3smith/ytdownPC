# Security audit input repair (2026-10-26)

The Monday full audit also examines existing dependencies and Git history.
Push/PR checks compare incoming changes against their base, so a successful
push check does not mean the full history or every existing dependency is clean.

Python manifests now contain the complete pinned dependency versions instead
of letting OSV's requirements resolver infer a different transitive environment.
The complete closure is still scanned, including indirect packages. The original
direct requirements are retained in `.in` files. This is not an advisory ignore
or a disabled vulnerability check. New and existing OSV findings still fail.

When dependencies change, regenerate the complete pinned requirements, validate
installation compatibility on the documented Python/platform, run application
regressions, and run the full audit (`python .github/scripts/security_checks.py audit`).
The audit now prints sanitized package/version/advisory identities so subsequent
failures are actionable without uploading raw reports or credential values.

Upstream scanner behavior and recommended lockfile inputs:
https://google.github.io/osv-scanner/supported-languages-and-lockfiles/

The workflows remain enabled for pushes, pull requests and weekly schedules.
Notifications, repository visibility and security permissions are unchanged.
These source/CI changes do not install or restart a running application and do
not replace previously published binaries.
