"""YTDownPC entry point; CLI/MCP APIs remain backward compatible."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from pc_storage import DEFAULT_OUTPUT,activate_library,read_private
activate_library()
from pc_engine import FORMAT_SELECTORS,QUALITY_LABELS,download_video,probe_video,validate_media_url,format_bytes
from version_info import APP_NAME,APP_VERSION
APP_TITLE=f'{APP_NAME} v{APP_VERSION}'
def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser(description=APP_TITLE)
    p.add_argument('--url');p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--quality',choices=list(FORMAT_SELECTORS),default='best')
    p.add_argument('--audio-only',action='store_true');p.add_argument('--probe',action='store_true')
    p.add_argument('--job-file',type=Path);p.add_argument('--log-file',type=Path)
    args=p.parse_args()
    def emit(e):print(json.dumps(e,ensure_ascii=False),flush=True)
    if args.job_file:
        sys.stdout=args.job_file.with_suffix('.events').open('w',encoding='utf-8',buffering=1)
        try:
            request=read_private(args.job_file);args.job_file.unlink(missing_ok=True)
            emit({'stage':'worker-result','result':download_video(progress=emit,**request)});return 0
        except Exception as exc:
            from pc_engine import redact
            emit({'stage':'worker-error','text':redact(str(exc))});return 1
    if args.url:
        emit(probe_video(args.url) if args.probe else download_video(args.url,args.output,args.quality,audio_only=args.audio_only));return 0
    if args.probe:p.error('--probe requires --url')
    from pc_gui import run
    return run()
if __name__=='__main__':raise SystemExit(main())
