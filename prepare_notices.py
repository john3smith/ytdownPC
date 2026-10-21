"""Copy dependency notices from installed packages; never collect runtime/user data."""
import importlib.metadata,json,subprocess,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent;dest=root/'docs/third-party';dest.mkdir(parents=True,exist_ok=True);rows=[]
for name in ['PySide6','PySide6_Essentials','PySide6_Addons','PySide6_WebEngine','PySide6_Pdf','shiboken6','yt-dlp','yt-dlp-ejs','curl-cffi','Pillow','certifi','cffi','pywin32','pyinstaller']:
    d=importlib.metadata.distribution(name);copied=[]
    for f in d.files or []:
        if '.dist-info/' not in str(f) or not any(x in str(f).lower() for x in ['license','copying','notice']):continue
        source=Path(d.locate_file(f))
        if source.is_file():
            target=dest/(name+'-'+source.name);target.write_bytes(source.read_bytes());copied.append(target.name)
    rows.append(dict(name=d.metadata['Name'],version=d.version,license=d.metadata.get('License-Expression') or d.metadata.get('License'),notices=copied))
for name,url in [('LGPL-3.0.txt','https://raw.githubusercontent.com/qt/qtbase/dev/LICENSES/LGPL-3.0-only.txt'),('GPL-3.0.txt','https://raw.githubusercontent.com/qt/qtbase/dev/LICENSES/GPL-3.0-only.txt')]:
    text=urllib.request.urlopen(url,timeout=30).read()
    assert b'GNU' in text and len(text)>3000;(dest/name).write_bytes(text)
version=subprocess.check_output(['node','--version'],creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
node=urllib.request.urlopen('https://raw.githubusercontent.com/nodejs/node/'+version+'/LICENSE',timeout=30).read();assert b'Node.js' in node;(dest/'Node-LICENSE.txt').write_bytes(node)
(dest/'dependency-inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
print('Dependency notices prepared:',len(rows))
