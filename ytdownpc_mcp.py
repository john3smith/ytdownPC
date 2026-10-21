"""Local stdio interface. Server startup never starts a download."""
import threading
from mcp.server import MCPServer
from ytdownpc import FORMAT_SELECTORS,probe_video,validate_media_url
from pc_queue import DownloadQueue
from pc_storage import settings
server=MCPServer('ytdownpc');_manager=None;_lock=threading.Lock()
def manager():
    global _manager
    with _lock:
        if _manager is None:_manager=DownloadQueue()
        return _manager
@server.tool()
def video_info(url:str)->dict:
    """Read public media metadata without downloading."""
    return probe_video(validate_media_url(url))
@server.tool()
def start_download(url:str,quality:str='best',audio_only:bool=False)->dict:
    """Enqueue public media or M4A extraction using the desktop output/Wi-Fi settings."""
    url=validate_media_url(url)
    if quality not in FORMAT_SELECTORS:raise ValueError('Unknown quality')
    opts=settings();opts.update(quality=quality,audio_only=audio_only,cookies=[])
    id=manager().enqueue(url,opts)
    return dict(job_id=id,status='queued',output_dir=opts['output'])
@server.tool()
def download_status(job_id:str)->dict:
    """Read completion, progress and actual final files (not only task startup)."""
    job=next((j for j in manager().snapshot() if j['id']==job_id),None)
    if job is None:raise ValueError('Unknown job ID; jobs do not survive a server restart')
    return dict(job_id=job_id,**job)
@server.tool()
def cancel_download(job_id:str)->dict:
    """Cancel one queued/active job and its child processes."""
    download_status(job_id);manager().cancel(job_id);return download_status(job_id)
if __name__=='__main__':
    try:server.run(transport='stdio')
    finally:
        if _manager:_manager.close()
