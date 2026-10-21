"""App-owned HTTPS viewer and explicitly initiated account media discovery."""
from __future__ import annotations
import json,re,time
from pathlib import Path
from urllib.parse import urlsplit
from PySide6.QtCore import QUrl,QTimer,Signal
from PySide6.QtWidgets import QMainWindow,QToolBar,QLineEdit,QLabel,QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile,QWebEngineSettings,QWebEngineScript,QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from pc_engine import validate_web_url,validate_media_url
from pc_storage import DATA_DIR
SITES={'YouTube':'https://www.youtube.com/','X':'https://x.com/','Instagram':'https://www.instagram.com/'}
class SecureRequests(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self,request):
        if request.requestUrl().scheme() not in {'https','data','blob','about'}:request.block(True)
class SecurePage(QWebEnginePage):
    def acceptNavigationRequest(self,url,type,isMainFrame):
        return url.scheme()=='https' or url.toString()=='about:blank'
    def createWindow(self,type):return self
class Sessions:
    def __init__(self,parent):self.parent=parent;self.profiles={};self.cookies={}
    def profile(self,site):
        if site not in self.profiles:
            path=DATA_DIR/'browser'/site;path.mkdir(parents=True,exist_ok=True)
            profile=QWebEngineProfile('YTDownPC-'+site,self.parent);profile.setPersistentStoragePath(str(path));profile.setCachePath(str(path/'cache'))
            profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
            profile.settings().setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent,False)
            interceptor=SecureRequests(profile);profile.setUrlRequestInterceptor(interceptor);profile._interceptor=interceptor
            self.cookies[site]={};store=profile.cookieStore()
            def added(c):
                k=(c.domain(),c.path(),bytes(c.name()))
                self.cookies[site][k]=dict(name=bytes(c.name()).decode('utf-8','replace'),value=bytes(c.value()).decode('utf-8','replace'),domain=c.domain(),path=c.path(),secure=c.isSecure(),expires=None if c.isSessionCookie() else c.expirationDate().toSecsSinceEpoch())
            def removed(c):self.cookies[site].pop((c.domain(),c.path(),bytes(c.name())),None)
            store.cookieAdded.connect(added);store.cookieRemoved.connect(removed);store.loadAllCookies();self.profiles[site]=profile
        return self.profiles[site]
    def snapshot(self):return [dict(c) for jar in self.cookies.values() for c in jar.values()]
    def clear(self,site):
        self.profile(site).cookieStore().deleteAllCookies();self.cookies[site].clear()
    def ready(self,site):return bool(self.cookies.get(site))

def account_url(url):
    p=urlsplit(validate_media_url(url));parts=p.path.strip('/').split('/');host=p.hostname.lower()
    if host.endswith('instagram.com'):
        if not re.fullmatch(r'[A-Za-z0-9_.]{1,30}',parts[0]) or parts[0] in {'p','reel','reels','tv','accounts','explore'}:raise ValueError('Instagram 계정 프로필 주소를 입력해 주세요.')
        return 'Instagram',parts[0],'https://www.instagram.com/'+parts[0]+'/'
    if host.endswith('x.com') or host.endswith('twitter.com'):
        if not re.fullmatch(r'[A-Za-z0-9_]{1,15}',parts[0]) or parts[0] in {'i','home','search','settings','intent'}:raise ValueError('X 계정 프로필 또는 게시물 주소를 입력해 주세요.')
        return 'X',parts[0],'https://x.com/'+parts[0]+'/media'
    raise ValueError('계정 미디어는 X·Instagram에서 지원합니다.')

class BrowserWindow(QMainWindow):
    discovered=Signal(str,list)
    scanFailed=Signal(str)
    def __init__(self,sessions,site,url,*,scan=False,parent=None):
        super().__init__(parent);self.setAttribute(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle('YTDownPC · '+('계정 미디어 검색' if scan else '현재 웹페이지 / 로그인'));self.resize(1050,780)
        self.site=site;self.scan=scan;self.done=False;self.scanning=False;self.started=0;self.stable=0;self.signature=None;self.pages={};self.phase='posts'
        self.view=QWebEngineView();self.page=SecurePage(sessions.profile(site),self.view);self.view.setPage(self.page);self.setCentralWidget(self.view)
        self.page.certificateError.connect(lambda e:e.rejectCertificate())
        self.page.permissionRequested.connect(lambda p:p.deny())
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,False)
        bar=QToolBar();bar.setMovable(False);self.addToolBar(bar)
        for text,call in [('뒤로',self.view.back),('새로고침',self.view.reload),('닫기',self.close)]:
            a=QAction(text,self);a.triggered.connect(call);bar.addAction(a)
        self.address=QLineEdit(url);self.address.returnPressed.connect(self.navigate);bar.addWidget(self.address)
        self.view.urlChanged.connect(lambda u:self.address.setText(u.toString()))
        self.state=QLabel('로그인·보안 확인은 직접 진행해 주세요.');self.statusBar().addWidget(self.state,1)
        self.timer=QTimer(self);self.timer.setInterval(1800);self.timer.timeout.connect(self.poll)
        if scan:
            self.site,self.username,self.target=account_url(url)
            script=QWebEngineScript();script.setName('YTDownPC account media observer');script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation);script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld);script.setSourceCode(Path(__file__).with_name('account_capture.js').read_text('utf-8'));self.page.scripts().insert(script)
            self.scanAction=QAction('계정 검색 시작',self);self.scanAction.triggered.connect(self.start_scan);bar.addAction(self.scanAction)
            self.view.load(QUrl(self.target))
        else:self.view.load(QUrl(validate_web_url(url)))
    def navigate(self):
        try:self.view.load(QUrl(validate_web_url(self.address.text())))
        except ValueError as e:QMessageBox.warning(self,'주소',str(e))
    def start_scan(self):
        if self.scanning:return
        self.scanning=True;self.started=time.monotonic();self.scanAction.setEnabled(False);self.view.load(QUrl(self.target));self.timer.start()
    def fail(self,message):
        self.timer.stop();self.scanning=False;self.state.setText(message);self.scanFailed.emit(message);self.done=True
    def poll(self):
        if not self.scanning:return
        if time.monotonic()-self.started>600:self.fail('검색 시간 제한: 부분 목록을 전체로 다운로드하지 않았습니다.');return
        current=self.view.url().toString()
        parsed=urlsplit(current);expected={'x.com','www.x.com','twitter.com','www.twitter.com'} if self.site=='X' else {'instagram.com','www.instagram.com'}
        if parsed.hostname not in expected or parsed.path.strip('/').split('/')[0].lower()!=self.username.lower():
            self.state.setText('계정 화면 이탈/로그인·확인 필요: 직접 완료 후 다시 검색해 주세요.');return
        self.page.runJavaScript("JSON.stringify({state:window.__pcMedia||null,height:document.documentElement.scrollHeight,links:[...document.querySelectorAll('a[href]')].map(a=>a.href)})",self.received)
    def received(self,raw):
        if not self.scanning:return
        try:d=json.loads(raw or '{}')
        except ValueError:return
        state=d.get('state') or {};posts=state.get('posts') or []
        for u in d.get('links',[]):
            if self.site=='X' and re.match(r'https://(?:x|twitter)\.com/'+re.escape(self.username)+r'/status/\d+',u,re.I):posts.append(u.split('?')[0].split('/photo/')[0].split('/video/')[0])
        for u in posts:
            try:
                validate_media_url(u)
                pattern=r'https://(?:www\.)?(?:x|twitter)\.com/'+re.escape(self.username)+r'/status/\d+$' if self.site=='X' else r'https://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?$'
                if re.fullmatch(pattern,u,re.I):self.pages[u]=None
            except ValueError:pass
        signature=(len(self.pages),d.get('height'),state.get('responses'))
        self.stable=self.stable+1 if signature==self.signature else 0;self.signature=signature
        self.state.setText(f'@{self.username}: {len(self.pages)}개 게시물 확인 · {self.phase} · 끝 확인 중')
        if state.get('ended') and self.pages:
            if self.site=='Instagram' and self.phase=='posts':
                self.phase='reels';self.signature=None;self.stable=0;self.view.load(QUrl(self.target+'reels/'));return
            self.timer.stop();self.scanning=False;self.done=True;self.discovered.emit(self.username,list(self.pages));self.close();return
        if self.stable>=18:
            self.fail('끝 페이지 확인 불가: 로그인/네트워크/사이트 구조를 확인하세요. 부분 목록은 전체로 처리하지 않았습니다.');return
        self.page.runJavaScript('window.scrollTo(0,document.documentElement.scrollHeight)')
    def closeEvent(self,event):
        self.timer.stop()
        if self.scan and not self.done:self.scanFailed.emit('계정 검색을 취소했습니다.')
        self.page.triggerAction(QWebEnginePage.WebAction.Stop);self.page.deleteLater();super().closeEvent(event)
