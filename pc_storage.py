"""Settings, encrypted session handoff and owned partial-file cleanup."""
from __future__ import annotations
import ctypes,hashlib,json,os,re,sys,time,urllib.request,zipfile
from ctypes import wintypes
from pathlib import Path
DATA_DIR=Path(os.environ.get('YTDOWNPC_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA',Path.home()))/'YTDownPC')
DEFAULT_OUTPUT=Path.home()/'Downloads'
DEFAULTS=dict(output=str(DEFAULT_OUTPUT),quality='best',audio_only=False,immediate=True,wifi_only=False,https_assist=False,auto_update=True)
def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8');os.replace(tmp,path)
def _json_object(path,limit=65536):
    try:
        with path.open(encoding='utf-8') as stream:raw=stream.read(limit+1)
        if len(raw)>limit:return {}
        value=json.loads(raw)
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError,RecursionError):return {}

def settings():
    result=dict(DEFAULTS);saved=_json_object(DATA_DIR/'settings.json')
    output=saved.get('output')
    if isinstance(output,str) and output.strip() and '\0' not in output and len(output)<=32767:result['output']=output
    quality=saved.get('quality')
    if isinstance(quality,str) and quality in {'best','1080','720'}:result['quality']=quality
    for key,default in DEFAULTS.items():
        if isinstance(default,bool) and type(saved.get(key)) is bool:result[key]=saved[key]
    return result
def save_settings(data):atomic_json(DATA_DIR/'settings.json',{k:data[k] for k in DEFAULTS if k in data})
def _dpapi(data,decrypt=False):
    class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data);src=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));dst=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32')
    if decrypt:ok=crypt.CryptUnprotectData(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dst))
    else:ok=crypt.CryptProtectData(ctypes.byref(src),'YTDownPC private data',None,None,None,1,ctypes.byref(dst))
    if not ok:raise OSError('Windows private data protection failed')
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    try:return ctypes.string_at(dst.data,dst.size)
    finally:kernel.LocalFree(dst.data)
def write_private(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=_dpapi(json.dumps(data,ensure_ascii=False).encode('utf-8'));tmp=path.with_suffix('.tmp');tmp.write_bytes(raw);os.replace(tmp,path)
def read_private(path):return json.loads(_dpapi(Path(path).read_bytes(),True).decode('utf-8'))
def _get(url,limit=40_000_000):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'YTDownPC-runtime'}),timeout=30) as r:data=r.read(limit+1)
    if len(data)>limit:raise ValueError('Runtime download exceeded size limit')
    return data
def update_library(force=False):
    with OutputLock(DATA_DIR/'runtime'):return _update_library(force)
def _update_library(force=False):
    marker=DATA_DIR/'library.json';dest=DATA_DIR/'runtime/yt-dlp.zip'
    old=_json_object(marker,8192);checked=old.get('checked',0);now=time.time()
    if (not force and type(checked) in (int,float)
            and 0<=checked<=now and now-checked<86400):return old
    release=json.loads(_get('https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest'))
    tag=release['tag_name'];assets={a['name']:a['browser_download_url'] for a in release['assets']}
    def asset(name):
        url=assets[name]
        if not url.startswith('https://github.com/yt-dlp/yt-dlp/releases/download/'):raise ValueError('Unexpected runtime source')
        return _get(url)
    checks=asset('SHA2-256SUMS').decode('utf-8');expected=next(line.split()[0] for line in checks.splitlines() if line.split()[-1].lstrip('*')=='yt-dlp')
    if old.get('version')==tag and dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()==expected:
        old['checked']=time.time();atomic_json(marker,old);return old
    data=asset('yt-dlp')
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('yt-dlp checksum mismatch')
    dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_suffix('.download');tmp.write_bytes(data)
    with zipfile.ZipFile(tmp) as z:
        if 'yt_dlp/__init__.py' not in z.namelist() or z.testzip():raise ValueError('Invalid runtime archive')
    os.replace(tmp,dest);record=dict(version=tag,sha256=expected,checked=time.time());atomic_json(marker,record);return record
def activate_library():
    try:
        record=_json_object(DATA_DIR/'library.json',8192);p=DATA_DIR/'runtime/yt-dlp.zip';expected=record.get('sha256')
        if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):return
        if hashlib.sha256(p.read_bytes()).hexdigest()==expected:sys.path.insert(0,str(p))
    except (OSError,ValueError,KeyError):pass
def ffmpeg_path():
    """Obtain the original upstream binary locally rather than repackaging it."""
    with OutputLock(DATA_DIR/'runtime'):return _ffmpeg_path()
def _ffmpeg_path():
    import shutil
    if existing:=shutil.which('ffmpeg'):return existing
    target=DATA_DIR/'runtime/ffmpeg.exe'
    if target.is_file():return str(target)
    index=json.loads(_get('https://pypi.org/pypi/imageio-ffmpeg/0.6.0/json'))
    wheel=next(x for x in index['urls'] if x['filename'].endswith('win_amd64.whl'))
    if not wheel['url'].startswith('https://files.pythonhosted.org/'):raise ValueError('Unexpected FFmpeg source')
    data=_get(wheel['url'],60_000_000)
    if hashlib.sha256(data).hexdigest()!=wheel['digests']['sha256']:raise ValueError('FFmpeg wheel checksum mismatch')
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name=next(n for n in z.namelist() if n.startswith('imageio_ffmpeg/binaries/') and n.endswith('.exe'));raw=z.read(name)
    target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix('.download');tmp.write_bytes(raw);os.replace(tmp,target)
    atomic_json(DATA_DIR/'runtime/ffmpeg-source.json',dict(wheel=wheel['filename'],wheel_sha256=wheel['digests']['sha256'],binary_sha256=hashlib.sha256(raw).hexdigest(),source='https://pypi.org/project/imageio-ffmpeg/0.6.0/'))
    return str(target)
def partial_files(output):
    base=Path(output).resolve()/'.ytdownpc-parts'
    if base.is_symlink() or (base.exists() and base.resolve()!=base):raise ValueError('Unsafe staging directory')
    rows=[]
    if base.is_dir():
        for p in base.iterdir():
            if p.is_symlink() or not p.is_file() or not re.search(r'(\.part(?:-Frag\d+)?|\.ytdl)$',p.name):continue
            st=p.stat();rows.append(dict(path=str(p),bytes=st.st_size,mtime_ns=st.st_mtime_ns))
    return rows
def delete_partial(output,record):
    base=Path(output).resolve()/'.ytdownpc-parts';p=Path(record['path'])
    if p.is_symlink() or p.parent!=base or p.resolve()!=p or base.resolve()!=base:return False
    if record not in partial_files(output):return False
    p.unlink();return True

class OutputLock:
    """Cross-process exclusion shared by UI/MCP downloads and explicit cleanup."""
    def __init__(self,output):self.base=Path(output).expanduser().resolve()/'.ytdownpc-parts';self.file=None
    def __enter__(self):
        import msvcrt
        if self.base.is_symlink() or (self.base.exists() and self.base.resolve()!=self.base):raise ValueError('Unsafe staging directory')
        self.base.mkdir(parents=True,exist_ok=True);path=self.base/'.active.lock'
        if path.is_symlink():raise ValueError('Unsafe lock file')
        self.file=path.open('a+b');self.file.seek(0)
        try:msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:self.file.close();self.file=None;raise RuntimeError('다른 YTDownPC 작업이 이 저장 폴더를 사용 중입니다.')
        return self
    def __exit__(self,*args):
        import msvcrt
        if self.file:self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1);self.file.close()
