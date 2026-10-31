"""Sequential queue with per-job snapshots and cancellable process trees."""
from __future__ import annotations
import copy,ctypes,json,os,subprocess,sys,threading,time,uuid
from pathlib import Path
from pc_engine import validate_media_url,redact
from pc_storage import DATA_DIR,write_private,update_library,delete_partial,OutputLock
def wifi_connected():
    """Use the WLAN connection state; do not infer Wi-Fi from adapter names."""
    if os.name!='nt':return False
    from ctypes import wintypes
    class Interface(ctypes.Structure):_fields_=[('guid',ctypes.c_byte*16),('description',wintypes.WCHAR*256),('state',wintypes.DWORD)]
    wlan=ctypes.WinDLL('wlanapi');handle=wintypes.HANDLE();version=wintypes.DWORD();ptr=ctypes.c_void_p()
    if wlan.WlanOpenHandle(2,None,ctypes.byref(version),ctypes.byref(handle)):return False
    try:
        if wlan.WlanEnumInterfaces(handle,None,ctypes.byref(ptr)):return False
        count=ctypes.cast(ptr,ctypes.POINTER(wintypes.DWORD))[0]
        rows=(Interface*count).from_address(ptr.value+8)
        return any(row.state==1 for row in rows)
    finally:
        if ptr:wlan.WlanFreeMemory(ptr)
        wlan.WlanCloseHandle(handle,None)
class ProcessTree:
    def __init__(self,command,stderr_callback=None):
        import win32job,win32api,win32con
        self.job=win32job.CreateJobObject(None,'YTDownPC-'+uuid.uuid4().hex)
        limits=win32job.QueryInformationJobObject(self.job,win32job.JobObjectExtendedLimitInformation)
        limits['BasicLimitInformation']['LimitFlags']=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(self.job,win32job.JobObjectExtendedLimitInformation,limits)
        self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE if stderr_callback else subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        self.stderr_thread=None
        if stderr_callback:
            def drain():
                count=0
                with self.process.stderr as stream:
                    while line:=stream.readline(8192):
                        if count<100:
                            try:stderr_callback(redact(line.decode('utf-8',errors='replace').strip()))
                            except Exception:pass
                        count+=1
            self.stderr_thread=threading.Thread(target=drain,daemon=True);self.stderr_thread.start()
        try:
            handle=win32api.OpenProcess(win32con.PROCESS_SET_QUOTA|win32con.PROCESS_TERMINATE,False,self.process.pid)
            try:win32job.AssignProcessToJobObject(self.job,handle)
            finally:handle.Close()
        except Exception:
            self.process.kill();self.process.wait();self.job.Close();raise
    def close(self):
        if self.job:self.job.Close();self.job=None
    def wait(self):
        result=self.process.wait()
        if self.stderr_thread:self.stderr_thread.join(2)
        return result
class DownloadQueue:
    def __init__(self,notify=lambda e:None,network=wifi_connected):
        self.notify=notify;self.network=network;self.lock=threading.RLock();self.jobs=[];self.closed=False;self.active=None
        self.thread=threading.Thread(target=self._loop,daemon=True,name='ytdownpc-queue');self.thread.start()
    def enqueue(self,url,options,*,links=None,account=None,reserve=False):
        url=validate_media_url(url)
        with self.lock:
            if self.closed:raise RuntimeError('종료 중입니다.')
            if sum(j['status'] in {'queued','running','waiting-wifi','discovering'} for j in self.jobs)>=11:raise RuntimeError('대기열은 진행 항목 외 최대10개입니다.')
            job=dict(id=uuid.uuid4().hex,url=url,options=copy.deepcopy(options),links=list(links or [url]),account=account,status='queued',cancel=False,progress=0,result=None,error=None,completed_items=0,failed_items=0,total_items=len(links or [url]))
            self.jobs.append(job)
            if reserve:job['status']='discovering'
        self.notify(dict(stage='queue-changed'));return job['id']
    def resolve(self,id,links,account,cookies):
        with self.lock:
            job=next(j for j in self.jobs if j['id']==id)
            if job['cancel']:return
            if not links:raise ValueError('계정 미디어 목록이 비어 있습니다.')
            job.update(links=list(dict.fromkeys(links)),account=account,status='queued',total_items=len(set(links)))
            job['options']['cookies']=copy.deepcopy(cookies)
        self.notify(dict(stage='queue-changed'))
    def snapshot(self):
        with self.lock:
            return [{k:copy.deepcopy(j[k]) for k in ['id','url','account','status','progress','result','error','completed_items','failed_items','total_items']} for j in self.jobs]
    def busy(self):
        with self.lock:return any(j['status'] in {'queued','running','waiting-wifi','discovering'} for j in self.jobs)
    def cleanup(self,output,rows):
        with self.lock:
            if self.busy():raise RuntimeError('실행/대기 작업이 있으면 삭제할 수 없습니다.')
            with OutputLock(output):return sum(delete_partial(output,r) for r in rows)
    def cancel(self,id=None):
        with self.lock:
            for j in self.jobs:
                if (id is None or j['id']==id) and j['status'] in {'queued','running','waiting-wifi','discovering'}:
                    j['cancel']=True
                    if self.active and self.active[0]==j['id']:self.active[1].close()
                    if j['status']!='running':j['status']='cancelled'
        self.notify(dict(stage='queue-changed'))
    def close(self):
        self.closed=True;self.cancel()
    def _run_item(self,job,url):
        id=uuid.uuid4().hex;request=DATA_DIR/'jobs'/f'{id}.bin';events=request.with_suffix('.events')
        opts=job['options'];payload={k:opts[k] for k in ['quality','audio_only','cookies','https_assist','user_agent'] if k in opts}
        payload.update(url=url,output_dir=opts['output']);write_private(request,payload)
        exe=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).with_name('ytdownpc.py'))]
        tree=None;result=None;error=None
        try:
            with self.lock:
                if job['cancel']:return None
                tree=ProcessTree(exe+['--job-file',str(request)],stderr_callback=lambda text:self.notify(dict(stage='message',text=text,job_id=job['id'])));self.active=(job['id'],tree)
            position=0;pending=''
            while True:
                if events.exists():
                    with events.open('r',encoding='utf-8') as f:f.seek(position);pending+=f.read();position=f.tell()
                    lines=pending.split('\n');pending=lines.pop()
                    for line in lines:
                        try:e=json.loads(line)
                        except ValueError:continue
                        if e.get('stage')=='worker-result':result=e['result']
                        elif e.get('stage')=='worker-error':error=e['text']
                        else:
                            with self.lock:job['progress']=min(99,float(e.get('percent') or job['progress']))
                            self.notify({**e,'job_id':job['id']})
                if tree.process.poll() is not None:
                    if not pending and (result or error or job['cancel']):break
                    # One final read after process exit and stream flush.
                    if getattr(tree,'drained',False):break
                    tree.drained=True
                time.sleep(.1)
            if job['cancel']:return None
            if not result:raise RuntimeError(error or '다운로드 프로세스가 완료 파일 없이 종료되었습니다.')
            return result
        finally:
            with self.lock:self.active=None
            if tree:tree.close();tree.wait()
            request.unlink(missing_ok=True);events.unlink(missing_ok=True)
    def _loop(self):
        while not self.closed:
            with self.lock:
                job=next((j for j in self.jobs if j['status'] in {'queued','waiting-wifi','discovering'}),None)
                if job and job['status']=='discovering':job=None
                if job and job['options'].get('wifi_only') and not self.network():
                    job['status']='waiting-wifi';job=None
                if job:job['status']='running'
            if not job:time.sleep(.3);continue
            self.notify(dict(stage='queue-changed'))
            try:
                if job['options'].get('auto_update'):
                    try:update_library();self.notify(dict(stage='message',text='다운로드 라이브러리 확인 완료'))
                    except Exception:self.notify(dict(stage='message',text='업데이트 확인 실패: 검증된 기존 라이브러리를 사용합니다.'))
                results=[]
                for link in job['links']:
                    if job['cancel'] or self.closed:break
                    try:
                        result=self._run_item(job,link)
                        if result:results.append(result);job['completed_items']+=1
                    except Exception as exc:
                        job['failed_items']+=1;job['error']=redact(str(exc));self.notify(dict(stage='message',text=job['error']))
                with self.lock:
                    job['result']=dict(files=[f for r in results for f in r['files']],artifacts=[a for r in results for a in r.get('artifacts',[])],title=job['account'] or (results[0]['title'] if results else '미디어'))
                    job['status']='cancelled' if job['cancel'] else 'failed' if job['failed_items'] else 'completed'
                    if job['status']=='completed':job['progress']=100
            except Exception as exc:
                job['error']=redact(str(exc));job['status']='cancelled' if job['cancel'] else 'failed'
            self.notify(dict(stage='queue-changed'))
