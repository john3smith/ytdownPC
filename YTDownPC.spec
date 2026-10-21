# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil
from PyInstaller.utils.hooks import collect_all
root=Path(SPECPATH);version={};exec((root/'version_info.py').read_text('utf-8'),version)
name=f"YTDownPC-v{version['APP_VERSION']}"
datas=[(str(root/'account_capture.js'),'.'),(str(root/'docs'),'docs'),(str(root/'THIRD_PARTY_NOTICES.md'),'.'),(str(root/'README.txt'),'.')];binaries=[];hiddenimports=[]
for package in ['yt_dlp','yt_dlp_ejs','curl_cffi']:
    d,b,h=collect_all(package);datas+=d;binaries+=b;hiddenimports+=h
node=shutil.which('node')
if not node:raise RuntimeError('Node.js is required to build the portable runtime')
binaries.append((node,'bin'))
a=Analysis([str(root/'ytdownpc.py')],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,hookspath=[str(root/'hooks')],hooksconfig={},runtime_hooks=[],excludes=['tkinter','imageio_ffmpeg','mcp','PySide6.QtPdf','PySide6.QtPdfWidgets'],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name=name,debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name=name)
