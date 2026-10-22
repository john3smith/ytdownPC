"""Read-only Windows release gate. Does not execute the candidate or alter trust."""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path

class ReleaseBlocked(ValueError):
    pass

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def inspect_signature(path):
    path=Path(path).resolve(strict=True)
    if not path.is_file():raise ReleaseBlocked('Expected a file')
    if sys.platform!='win32':raise ReleaseBlocked('Windows Authenticode verification is required')
    env=os.environ.copy();env['RELEASE_SIGNATURE_FILE']=str(path)
    # Fixed read-only cmdlet. No candidate file is executed, and no policy override.
    command="""$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);$s=Get-AuthenticodeSignature -LiteralPath $env:RELEASE_SIGNATURE_FILE;[pscustomobject]@{status=[string]$s.Status;signature_type=[string]$s.SignatureType;timestamped=[bool]$s.TimeStamperCertificate;signer_thumbprint=if($s.SignerCertificate){$s.SignerCertificate.Thumbprint}else{$null};self_issued=if($s.SignerCertificate){$s.SignerCertificate.Subject -eq $s.SignerCertificate.Issuer}else{$null};code_signing_eku=if($s.SignerCertificate){[bool]($s.SignerCertificate.EnhancedKeyUsageList.ObjectId.Value -contains '1.3.6.1.5.5.7.3.3')}else{$false}}|ConvertTo-Json -Compress"""
    r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],env=env,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=90)
    if r.returncode:raise ReleaseBlocked('Windows signature inspection failed')
    return json.loads(r.stdout.decode('utf-8-sig'))

def validate_policy(record,expected_thumbprint):
    if not re.fullmatch(r'[A-Fa-f0-9]{40}',expected_thumbprint or ''):
        raise ReleaseBlocked('An owner-approved certificate thumbprint is required')
    if record.get('status')!='Valid':raise ReleaseBlocked('Authenticode status: '+str(record.get('status')))
    if record.get('signature_type')!='Authenticode':raise ReleaseBlocked('An embedded Authenticode signature is required')
    if not record.get('timestamped'):raise ReleaseBlocked('A trusted timestamp is required')
    if not record.get('code_signing_eku'):raise ReleaseBlocked('The signer must have code-signing EKU')
    if record.get('self_issued') is not False:raise ReleaseBlocked('A self-issued test identity is not accepted for production')
    if (record.get('signer_thumbprint') or '').upper()!=expected_thumbprint.upper():
        raise ReleaseBlocked('Unexpected signing certificate')

def verify(path,expected_thumbprint,signtool):
    path=Path(path).resolve(strict=True);before=digest(path)
    record=inspect_signature(path);validate_policy(record,expected_thumbprint)
    if not signtool:raise ReleaseBlocked('Microsoft SignTool is required for final policy/timestamp verification')
    tool=Path(signtool).resolve(strict=True)
    # The user must supply the official SDK SignTool path, never an arbitrary helper.
    if tool.name.lower()!='signtool.exe' or inspect_signature(tool).get('status')!='Valid':
        raise ReleaseBlocked('A trusted Microsoft SDK SignTool binary is required')
    r=subprocess.run([str(tool),'verify','/pa','/all','/tw','/v',str(path)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
    if r.returncode:raise ReleaseBlocked('SignTool policy/timestamp verification failed or warned')
    if digest(path)!=before:raise ReleaseBlocked('File changed during verification')
    return dict(record,filename=path.name,bytes=path.stat().st_size,sha256=before,verified=True,signtool_policy='Authenticode /pa /all /tw')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file',type=Path);p.add_argument('--expected-thumbprint');p.add_argument('--signtool',type=Path)
    p.add_argument('--inspect-only',action='store_true');p.add_argument('--receipt',type=Path)
    args=p.parse_args()
    if args.inspect_only:
        record=dict(inspect_signature(args.file),filename=args.file.name,sha256=digest(args.file),verified=False,inspection_only=True)
    else:record=verify(args.file,args.expected_thumbprint,args.signtool)
    if args.receipt:
        with args.receipt.open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
    print(json.dumps(record));return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ReleaseBlocked,OSError,subprocess.SubprocessError,json.JSONDecodeError) as error:
        print(json.dumps({'verified':False,'blocked':str(error)}));raise SystemExit(2)
