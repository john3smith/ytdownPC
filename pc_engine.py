"""Media engine shared by the desktop UI, CLI and MCP."""
from __future__ import annotations
import copy,http.cookiejar,json,os,re,urllib.parse
from pathlib import Path
import yt_dlp
from yt_dlp.extractor.twitter import TwitterIE
from yt_dlp.extractor.instagram import InstagramIE
from yt_dlp.networking import Request
from yt_dlp.utils import sanitize_filename
from pc_storage import ffmpeg_path
QUALITY_LABELS={'최고 화질':'best','1080p 이하':'1080','720p 이하':'720'}
FORMAT_SELECTORS={
 'best':'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b',
 **{q:f'bv*[height<={q}][ext=mp4]+ba[ext=m4a]/b[height<={q}][ext=mp4]/bv*[height<={q}]+ba/b[height<={q}]' for q in ['1080','720']}}
HOSTS={'youtube.com','youtu.be','instagram.com','x.com','twitter.com','t.co'}
def validate_media_url(value):
    url=value.strip();p=urllib.parse.urlsplit(url);host=(p.hostname or '').lower()
    if p.scheme not in {'https','http'} or p.username or p.password or p.port not in {None,80,443} or not any(host==h or host in {'www.'+h,'m.'+h,'mobile.'+h,'music.'+h} for h in HOSTS):raise ValueError('YouTube·Instagram·X의 미디어 주소를 입력해 주세요.')
    return url
def validate_web_url(value):
    p=urllib.parse.urlsplit(value.strip())
    if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('웹페이지는 HTTPS 주소만 열 수 있습니다.')
    return value.strip()
def format_bytes(value):
    size=float(value or 0)
    for unit in ['B','KB','MB','GB','TB']:
        if size<1024 or unit=='TB':return f'{size:.1f} {unit}'
        size/=1024
def redact(text):
    text=re.sub(r'https?://[^\s<>"\']+','[URL]',str(text))
    text=re.sub(r'(?i)(cookie|authorization|password|token)\s*[:=]\s*[^\r\n]+',r'\1=[숨김]',text)
    text=re.sub(r'(?i)[A-Z]:[\\/][^\r\n"\']+','[로컬 경로]',text)
    return text[-2500:]
class QuietLogger:
    def __init__(self,emit):self.emit=emit
    def debug(self,m):pass
    def info(self,m):pass
    def warning(self,m):self.emit({'stage':'message','text':redact(m)})
    error=warning

def photo_info(url,id,title):
    return dict(id=str(id),title=title,_ytdown_photo=url,formats=[dict(url=url,ext='jpg',format_id='photo')])
class TwitterPhotosIE(TwitterIE):
    @classmethod
    def ie_key(cls):return 'Twitter'
    def _extract_status(self,id):
        if getattr(self,'_pc_status_id',None)!=id:
            self._pc_status=super()._extract_status(id);self._pc_status_id=id
        return copy.deepcopy(self._pc_status)
    def _real_extract(self,url):
        id=self._match_id(url);status=self._extract_status(id)
        media=status.get('extended_entities',{}).get('media',[])
        photos=[photo_info(urllib.parse.urlunsplit((*urllib.parse.urlsplit(m['media_url_https'])[:3],'name=orig','')),f'{id}-photo-{i}',f'X {id} 사진 {i}') for i,m in enumerate(media,1) if m.get('type')=='photo' and m.get('media_url_https')]
        if not photos:return super()._real_extract(url)
        entries=[]
        if any(m.get('type')!='photo' for m in media):
            result=super()._real_extract(url);entries=list(result['entries']) if result.get('_type')=='playlist' else [result]
        return dict(_type='playlist',id=id,title=f'X {id}',entries=entries+photos)
class InstagramPhotosIE(InstagramIE):
    @classmethod
    def ie_key(cls):return 'Instagram'
    def _extract_product_media(self,media):
        if not media.get('video_versions') and not media.get('video_dash_manifest'):
            candidates=media.get('image_versions2',{}).get('candidates',[])
            if candidates:
                best=max(candidates,key=lambda c:int(c.get('width',0))*int(c.get('height',0)))
                return photo_info(best['url'],media.get('pk') or media.get('id'),'Instagram 사진')
        return super()._extract_product_media(media)
    def _extract_nodes(self,nodes,is_direct=False):
        for i,node in enumerate(nodes,1):
            if node.get('__typename')!='GraphVideo' and node.get('is_video') is not True and node.get('display_url'):
                yield photo_info(node['display_url'],node.get('shortcode') or node.get('id') or i,f'Instagram 사진 {i}')
            else:yield from super()._extract_nodes([node],is_direct)

def add_cookies(ydl,cookies):
    for c in cookies or []:
        domain=c.get('domain','').lstrip('.').lower()
        if not any(domain==h or domain.endswith('.'+h) for h in HOSTS):continue
        ydl.cookiejar.set_cookie(http.cookiejar.Cookie(0,c['name'],c['value'],None,False,c['domain'],True,c['domain'].startswith('.'),c.get('path') or '/',True,bool(c.get('secure')),c.get('expires'),not bool(c.get('expires')),None,None,{},False))
def create_ydl(options,cookies=None):
    ydl=yt_dlp.YoutubeDL(options);add_cookies(ydl,cookies)
    ydl.add_info_extractor(TwitterPhotosIE(ydl));ydl.add_info_extractor(InstagramPhotosIE(ydl));return ydl
def probe_video(url,cookies=None):
    with create_ydl(dict(quiet=True,no_warnings=True,noplaylist=True,skip_download=True,logger=QuietLogger(lambda e:None)),cookies) as ydl:
        info=ydl.extract_info(validate_media_url(url),download=False,process=False)
    return {k:info.get(k) for k in ['id','title','channel','uploader_id','live_status']}

def valid_image_url(url):
    p=urllib.parse.urlsplit(url);h=(p.hostname or '').lower()
    return p.scheme=='https' and not p.username and p.port in {None,443} and any(h==d or h.endswith('.'+d) for d in ['twimg.com','cdninstagram.com','fbcdn.net'])
def download_photo(ydl,info,output,temp,emit):
    from PIL import Image
    url=info['_ytdown_photo']
    if not valid_image_url(url):raise ValueError('지원하지 않는 사진 원본 도메인입니다.')
    name=sanitize_filename(info.get('title') or '사진',restricted=False)[:100]+' ['+sanitize_filename(str(info['id']),restricted=True)[:60]+']'
    part=temp/(name+'.part');final=output/(name+'.jpg')
    if final.is_file():
        with Image.open(final) as image:image.verify()
        return final
    with ydl.urlopen(Request(url)) as response,part.open('wb') as f:
        if not valid_image_url(response.url):raise ValueError('사진 리디렉션 도메인을 확인할 수 없습니다.')
        total=int(response.headers.get('Content-Length') or 0);size=0
        if total>100_000_000:raise ValueError('사진 크기가 허용 범위를 넘었습니다.')
        while chunk:=response.read(128*1024):
            f.write(chunk);size+=len(chunk)
            if size>100_000_000:raise ValueError('사진 크기가 허용 범위를 넘었습니다.')
            emit(dict(stage='downloading',percent=min(99,size/total*100) if total else 0,downloaded=size,total=total))
    with Image.open(part) as image:
        image.verify();ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','GIF':'.gif'}.get(image.format)
    if not ext:raise ValueError('지원하지 않는 사진 형식입니다.')
    final=output/(name+ext)
    if final.exists():part.unlink()
    else:os.replace(part,final)
    return final

def download_video(url,output_dir,quality='best',progress=None,*,audio_only=False,cookies=None,https_assist=False):
    from pc_storage import OutputLock
    validate_media_url(url)
    with OutputLock(output_dir):return _download_video(url,output_dir,quality,progress,audio_only=audio_only,cookies=cookies,https_assist=https_assist)
def _download_video(url,output_dir,quality='best',progress=None,*,audio_only=False,cookies=None,https_assist=False):
    url=validate_media_url(url)
    if quality not in FORMAT_SELECTORS:raise ValueError('지원하지 않는 화질입니다.')
    output=Path(output_dir).expanduser().resolve();output.mkdir(parents=True,exist_ok=True)
    temp=output/'.ytdownpc-parts'
    if temp.is_symlink() or (temp.exists() and temp.resolve()!=temp):raise ValueError('안전하지 않은 임시 경로입니다.')
    temp.mkdir(exist_ok=True);emit=progress or (lambda e:None);files=[];last=[None]
    def hook(d):
        status=d.get('status')
        if status=='downloading':
            n=int(d.get('downloaded_bytes') or 0);total=int(d.get('total_bytes') or d.get('total_bytes_estimate') or 0);pct=min(99,n/total*100) if total else 0
            key=(int(pct),n//(1024*1024))
            if key==last[0]:return
            last[0]=key;emit(dict(stage='downloading',percent=pct,downloaded=n,total=total,speed=d.get('speed'),eta=d.get('eta')))
        elif status=='finished':emit(dict(stage='processing',percent=99))
    def post(d):
        if d.get('status')=='finished':
            path=d.get('info_dict',{}).get('filepath')
            if path:files.append(path)
    mode='audio' if audio_only else 'video-'+quality
    options=dict(format='bestaudio/best' if audio_only else FORMAT_SELECTORS[quality],paths=dict(home=str(output),temp=str(temp)),outtmpl={'default':f'%(title).160B [%(id)s]-{mode}.%(ext)s'},merge_output_format='mp4',ffmpeg_location=ffmpeg_path(),windowsfilenames=True,noplaylist=True,continuedl=True,overwrites=False,retries=3,fragment_retries=3,socket_timeout=25,concurrent_fragment_downloads=4,quiet=True,no_warnings=False,progress_hooks=[hook],postprocessor_hooks=[post],logger=QuietLogger(emit))
    import shutil,sys
    node=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'bin/node.exe'
    if node.is_file() or shutil.which('node'):options['js_runtimes']={'node':{'path':str(node) if node.is_file() else shutil.which('node')}}
    if audio_only:options['postprocessors']=[dict(key='FFmpegExtractAudio',preferredcodec='m4a',preferredquality='0')]
    if https_assist:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        options['impersonate']=ImpersonateTarget(client='chrome')
    emit(dict(stage='preparing',percent=0))
    with create_ydl(options,cookies) as ydl:
        root=ydl.extract_info(url,download=False,process=False)
        emit(dict(stage='metadata',title=root.get('title') or '미디어'))
        def process(info):
            if info is None:raise RuntimeError('빈 미디어 응답입니다.')
            if info.get('_type') in {'playlist','multi_video'}:
                count=0
                for entry in info['entries']:process(entry);count+=1
                if not count:raise RuntimeError('미디어 항목이 없습니다.')
            elif info.get('_type') in {'url','url_transparent'}:
                process(ydl.extract_info(info['url'],download=False,process=False))
            elif info.get('_ytdown_photo'):
                if audio_only:return
                files.append(str(download_photo(ydl,info,output,temp,emit)))
            else:
                done=ydl.process_ie_result(info,download=True)
                candidates=[done.get('filepath'),done.get('_filename'),ydl.prepare_filename(done)]
                candidates.extend(x.get('filepath') for x in done.get('requested_downloads',[]))
                if audio_only:candidates.extend(str(Path(x).with_suffix('.m4a')) for x in candidates[:] if x)
                else:candidates.extend(str(Path(x).with_suffix('.mp4')) for x in candidates[:] if x)
                files.extend(x for x in candidates if x and Path(x).is_file() and Path(x).resolve().parent==output)
        process(root)
    files=list(dict.fromkeys(str(Path(f).resolve()) for f in files if Path(f).is_file() and Path(f).stat().st_size>0 and Path(f).resolve().parent==output))
    if audio_only:files=[f for f in files if Path(f).suffix=='.m4a']
    if not files:raise RuntimeError('추출할 음원이 없거나 완료된 M4A 파일을 확인하지 못했습니다.' if audio_only else '완료된 미디어 파일을 확인하지 못했습니다.')
    result=dict(id=root.get('id'),title=root.get('title') or '미디어',channel=root.get('channel') or root.get('uploader') or '',file=files[0],files=files)
    emit(dict(stage='complete',percent=100,**result));return result
