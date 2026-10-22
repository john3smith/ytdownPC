param(
    [Parameter(Mandatory=$true)][string]$InputExe,
    [Parameter(Mandatory=$true)][string]$OutputExe,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{40}$')][string]$CertificateThumbprint,
    [Parameter(Mandatory=$true)][string]$TimestampUrl,
    [Parameter(Mandatory=$true)][string]$SignTool
)
$ErrorActionPreference='Stop'
$source=(Resolve-Path -LiteralPath $InputExe).Path
$tool=(Resolve-Path -LiteralPath $SignTool).Path
$destination=[IO.Path]::GetFullPath($OutputExe)
if (Test-Path -LiteralPath $destination) { throw 'Output already exists; never overwrite an existing signed/released file.' }
if ($source -eq $destination -or [IO.Path]::GetExtension($source) -ne '.exe') { throw 'Use a separate new EXE path.' }
$uri=[Uri]$TimestampUrl
if ($uri.Scheme -ne 'https' -or $uri.UserInfo) { throw 'Provide the approved HTTPS RFC3161 timestamp endpoint without credentials.' }
$cert=Get-Item -LiteralPath ('Cert:\CurrentUser\My\'+$CertificateThumbprint)
if (-not $cert.HasPrivateKey -or $cert.NotAfter -le (Get-Date) -or $cert.NotBefore -gt (Get-Date)) { throw 'Usable code signing certificate/private key is not available.' }
if ($cert.Subject -eq $cert.Issuer) { throw 'A self-signed test certificate is not accepted for production.' }
if (-not ($cert.EnhancedKeyUsageList.ObjectId.Value -contains '1.3.6.1.5.5.7.3.3')) { throw 'Certificate is not authorized for code signing.' }
$chain=New-Object Security.Cryptography.X509Certificates.X509Chain
$chain.ChainPolicy.RevocationMode=[Security.Cryptography.X509Certificates.X509RevocationMode]::Online
if (-not $chain.Build($cert)) { throw 'Certificate trust/revocation validation failed.' }
[IO.File]::Copy($source,$destination,$false)
& $tool sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $destination
if ($LASTEXITCODE -ne 0) { throw 'Signing failed. Preserve this separate output for diagnosis; do not publish it.' }
& $tool verify /pa /all /tw /v $destination
if ($LASTEXITCODE -ne 0) { throw 'Signature/timestamp verification failed; do not publish.' }
$signature=Get-AuthenticodeSignature -LiteralPath $destination
if ($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate -or $signature.SignerCertificate.Thumbprint -ne $CertificateThumbprint) { throw 'Verified signer/timestamp does not match the approved certificate.' }
[PSCustomObject]@{File=$destination;Status=[string]$signature.Status;SignerThumbprint=$signature.SignerCertificate.Thumbprint;Timestamped=$true;SHA256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash} | ConvertTo-Json
# Rebuild the final folder inventory/hash receipts after signing and before ZIP/release publication.
