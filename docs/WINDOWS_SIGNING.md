# Windows production signing — pending certificate provisioning

The existing public/downloadable binary is unsigned. Adding these tools does
not sign or replace it. No code-signing private key was available in the checked
CurrentUser/My or LocalMachine/My stores on 2026-10-22. USB/remote signing services
need the owner's identification and configuration; they were not probed with
credentials. Microsoft SDK SignTool was not found on PATH or the standard SDK path.

## Required identity and build order

Use an owner-approved CA-issued code-signing identity, hardware-backed or an
eligible signing service. Do not create a self-signed production certificate,
install a custom root, disable execution policy, or pass passwords in commands.
Code signing does not guarantee the absence of SmartScreen/reputation warnings.

1. Build and validate a new version in staging. Preserve running services and
   prior released files. Do not change historical assets or overwrite them.
2. Use the official SDK SignTool and a SHA-256 digest plus RFC3161 timestamp.
   `tools/sign_release.ps1` supports a certificate already exposed in
   CurrentUser/My (including supported hardware-key providers). Provide only
   its public thumbprint, the approved timestamp HTTPS URL, and explicit input,
   new output, and SignTool paths. It never imports a PFX or invents credentials.
   A service with a different signing provider requires its approved integration.
   Respect local PowerShell execution policy; do not bypass it to run the helper.
3. Run the independent verifier against the **final signed bytes**:

   `python tools/verify_authenticode.py NEW.exe --expected-thumbprint APPROVED_CERT_THUMBPRINT --signtool OFFICIAL_SIGNTOOL_PATH --receipt NEW.signature.json`

   The trusted fingerprint must come from the owner-approved certificate record,
   not be copied from an untrusted candidate. The verifier rejects unsigned,
   untrusted, modified, wrong-publisher, untimestamped, and catalog-only files.
   Final verification includes SignTool `/pa /all /tw` and requires no warnings.
   It does not launch the candidate or change certificate stores.
4. For portable folders, replace the main EXE only in a fresh staging copy,
   preserve dependency files/notices, regenerate file hashes and inventories
   **after signing**, and then package. A ZIP is not Authenticode-signed simply
   because its inner EXE is signed. Verify the EXE after extracting the final ZIP.
5. Publish only after product-specific checks pass. Record signing certificate,
   timestamp, final SHA-256 and GitHub asset receipt. Keep private keys, PFX files,
   hardware PINs, passwords and service authentication outside this repository.

Inspection-only: `python tools/verify_authenticode.py FILE.exe --inspect-only`.
It always reports `verified:false`; it is not a release approval.
Run policy tests with `PYTHONPATH=tools` and `python -m unittest discover -s tests -p test_authenticode_gate.py`.

## Current limits

The negative-path tests and actual unsigned-binary rejection do not prove a
successful production signing operation. Trusted signing/timestamp verification
and new signed binaries remain pending. Other product gates still apply.
For ipchanger, protected installation and real NIC/UAC recovery checks remain
separate blockers; editing PRODUCT-GATE.json cannot replace a signature check.
For homework, this preparation does not rebuild/restart the live MarketNotifier;
follow AGENTS.md when a functional executable is actually rebuilt and activated.

Official references:
- https://learn.microsoft.com/windows/win32/seccrypto/signtool
- https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options
- https://learn.microsoft.com/azure/artifact-signing/quickstart
