"""Render the UTF-8 README as a standalone HTML guide."""
import html,re
from pathlib import Path
from version_info import APP_VERSION
root=Path(__file__).resolve().parent;target=root/'docs/user-guide.html'
css=re.search(r'<style>(.*?)</style>',target.read_text('utf-8'),re.S)[1]
def inline(s):
    s=html.escape(s);s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s);s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',s)
def render(text):
    result=[];lines=text.strip().splitlines();i=0
    while i<len(lines):
        line=lines[i]
        if line.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):code.append(lines[i]);i+=1
            result.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>')
        elif line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].startswith('|'):
                cells=lines[i].strip('|').split('|')
                if not all(re.fullmatch(r'\s*:?-+:?\s*',c) for c in cells):rows.append(cells)
                i+=1
            result.append('<div style="overflow:auto"><table style="border-collapse:collapse;width:100%">'+''.join('<tr>'+''.join('<'+('th' if n==0 else 'td')+' style="padding:12px;border:1px solid #dbe5e6;text-align:left">'+inline(c.strip())+'</'+('th' if n==0 else 'td')+'>' for c in row)+'</tr>' for n,row in enumerate(rows))+'</table></div>');continue
        elif line.startswith('- '):result.append('<p>• '+inline(line[2:])+'</p>')
        elif line.strip():result.append('<p>'+inline(line)+'</p>')
        i+=1
    return ''.join(result)
parts=(root/'README.md').read_text('utf-8').split('\n## ');sections=[];nav=[]
for i,part in enumerate(parts[1:],1):
    title,text=part.split('\n',1);sections.append(f'<section id="section-{i}"><h2>{inline(title)}</h2>{render(text)}</section>');nav.append(f'<a href="#section-{i}">{inline(title)}</a>')
target.write_text('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>YTDownPC '+APP_VERSION+' 사용 설명서</title><style>'+css+'</style></head><body><header class="hero"><div class="eyebrow">YTDOWNPC / 2026.10.31</div><h1>영상·사진·음원, PC에서도.</h1><p>YTDownPC '+APP_VERSION+' · Android판 기능을 Windows 작업 흐름에 맞췄습니다.</p><div class="chips"><span class="chip">M4A·사진·대기열</span><span class="chip">로그인·계정 미디어 검색</span><span class="chip">실제 로그인 계정 전체 수집은 추가 확인 필요</span></div></header><div class="layout"><aside><nav>'+''.join(nav)+'</nav></aside><main>'+''.join(sections)+'</main></div><footer>외부 폰트/스크립트 없는 독립형 HTML · 최신 제한은 README와 Release 설명을 확인하세요.</footer></body></html>','utf-8')
assert '???' not in target.read_text('utf-8')
print('UTF-8 HTML guide generated')
