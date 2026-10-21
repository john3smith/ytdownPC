"""Native desktop adaptation of YTDown's download, login and queue controls."""
from __future__ import annotations
import json,os,threading,time
from pathlib import Path
from urllib.parse import urlsplit
from PySide6.QtCore import Qt,QTimer,Signal,QObject,QUrl
from PySide6.QtGui import QDesktopServices,QAction
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QComboBox,QCheckBox,QProgressBar,QTabWidget,QListWidget,QPlainTextEdit,QFileDialog,QMessageBox,QSystemTrayIcon,QMenu,QStyle)
from pc_storage import DATA_DIR,settings,save_settings,partial_files,update_library
from pc_engine import QUALITY_LABELS,validate_media_url,validate_web_url,format_bytes,redact,probe_video
from pc_queue import DownloadQueue
from pc_browser import Sessions,BrowserWindow,SITES,account_url
from version_info import APP_VERSION
class Signals(QObject):event=Signal(dict)
class DownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('YTDownPC v'+APP_VERSION);self.resize(940,800);self.setMinimumSize(760,680)
        self.signals=Signals();self.signals.event.connect(self.apply_event);self.manager=DownloadQueue(self.signals.event.emit);self.sessions=Sessions(self);self.windows=[];self.logs=[];self.last_cancel=0;self.configuration=settings();self.seen_completed=set();self.setAcceptDrops(True)
        self.setStyleSheet('QMainWindow,QWidget{background:#f4f7fa;color:#182e3c;font:10pt "Malgun Gothic"} QPushButton{background:#e3ebf2;border:0;border-radius:7px;padding:9px 14px} QPushButton:hover{background:#d0e1ef} QLineEdit,QComboBox,QListWidget,QPlainTextEdit{background:white;border:1px solid #cfdae2;border-radius:5px;padding:6px} QProgressBar{border:0;background:#dae5ee;border-radius:5px;text-align:center} QProgressBar::chunk{background:#087f8c;border-radius:5px} QTabBar::tab{padding:10px 22px} QLabel#heading{font-size:25px;font-weight:bold;color:#007b85}')
        host=QWidget();self.setCentralWidget(host);layout=QVBoxLayout(host);layout.setContentsMargins(24,18,24,18);layout.setSpacing(12)
        heading=QLabel('YTDownPC  '+APP_VERSION);heading.setObjectName('heading');layout.addWidget(heading)
        layout.addWidget(QLabel('영상·사진·M4A 음원  |  작업별 설정 유지  |  최대 10개 대기'))
        login=QHBoxLayout();self.site=QComboBox();self.site.addItems(SITES);login.addWidget(self.site)
        self.button(login,'로그인 / 웹페이지',self.login);self.button(login,'선택 사이트 세션 쿠키 지우기',self.clear_login);self.login_status=QLabel('앱 전용 세션');login.addWidget(self.login_status);login.addStretch();layout.addLayout(login)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        main=QWidget();body=QVBoxLayout(main);body.setSpacing(14);self.tabs.addTab(main,'다운로드')
        body.addWidget(QLabel('YouTube · X · Instagram 주소'))
        row=QHBoxLayout();self.url=QLineEdit();self.url.setPlaceholderText('링크를 붙여넣거나 끌어 놓으세요.');self.url.returnPressed.connect(self.enqueue);row.addWidget(self.url,1);self.button(row,'붙여넣기',self.paste);self.button(row,'현재 웹페이지 보기',self.webpage);body.addLayout(row)
        row=QHBoxLayout();self.immediate=QCheckBox('붙여넣기·드롭 후 바로 다운로드');self.wifi=QCheckBox('Wi-Fi에서만 시작');row.addWidget(self.immediate);row.addWidget(self.wifi);row.addStretch();body.addLayout(row)
        row=QHBoxLayout();self.audio=QCheckBox('음원만 추출 (M4A)');row.addWidget(self.audio);self.quality=QComboBox();self.quality.addItems(QUALITY_LABELS);row.addWidget(self.quality);self.assist=QCheckBox('HTTPS 연결 보조');row.addWidget(self.assist);row.addStretch();body.addLayout(row)
        self.assist.setToolTip('Windows의 curl 기반 브라우저 통신을 사용합니다. 인증서 검증은 유지합니다. Android 로컬 TLS 릴레이와 구현이 다릅니다.')
        row=QHBoxLayout();self.output=QLineEdit(self.configuration['output']);row.addWidget(self.output,1);self.button(row,'저장 폴더 선택',self.folder);self.button(row,'폴더 열기',self.open_folder);body.addLayout(row)
        self.title=QLabel('미디어 대기 중');self.title.setWordWrap(True);body.addWidget(self.title)
        self.progress=QProgressBar();self.progress.setRange(0,100);body.addWidget(self.progress);self.status=QLabel('대기 중');self.status.setWordWrap(True);body.addWidget(self.status)
        row=QHBoxLayout();self.download_button=self.button(row,'다운로드 / 대기열 추가',self.enqueue);self.download_button.setStyleSheet('background:#087f8c;color:white;font-weight:bold;padding:12px')
        self.button(row,'X·Instagram 계정 전체 미디어',self.account);self.button(row,'전체 취소 (빠르게 두 번)',self.cancel_all);body.addLayout(row)
        row=QHBoxLayout();self.button(row,'미완료 파일 조회 / 삭제',self.incomplete);self.button(row,'사용 방법',self.help);row.addStretch();body.addLayout(row)
        self.auto_update=QCheckBox('첫 작업 전 최신 stable 다운로드 라이브러리 확인 (하루 1회)');body.addWidget(self.auto_update)
        self.button(body,'다운로드 라이브러리 지금 업데이트',self.update);body.addStretch()
        queue_page=QWidget();ql=QVBoxLayout(queue_page);self.queue_list=QListWidget();ql.addWidget(self.queue_list);self.button(ql,'선택 항목 취소',self.cancel_selected);ql.addWidget(QLabel('계정 검색도 한 작업으로 예약됩니다. 검색 종료 후 뒤 작업을 이어갑니다.'));self.tabs.addTab(queue_page,'대기열 / 내역')
        log_page=QWidget();ll=QVBoxLayout(log_page);self.log=QPlainTextEdit();self.log.setReadOnly(True);ll.addWidget(self.log);self.button(ll,'로그 복사',lambda:QApplication.clipboard().setText(self.log.toPlainText()));self.tabs.addTab(log_page,'진단 로그')
        self.immediate.setChecked(self.configuration['immediate']);self.wifi.setChecked(self.configuration['wifi_only']);self.audio.setChecked(self.configuration['audio_only']);self.assist.setChecked(self.configuration['https_assist']);self.auto_update.setChecked(self.configuration['auto_update'])
        self.quality.setCurrentText(next((k for k,v in QUALITY_LABELS.items() if v==self.configuration['quality']),'최고 화질'));self.quality.setEnabled(not self.audio.isChecked())
        self.audio.toggled.connect(lambda on:self.quality.setEnabled(not on))
        for c in [self.immediate,self.wifi,self.audio,self.assist,self.auto_update]:c.toggled.connect(self.persist)
        self.quality.currentTextChanged.connect(self.persist);self.output.editingFinished.connect(self.persist)
        self.timer=QTimer(self);self.timer.setInterval(500);self.timer.timeout.connect(self.refresh);self.timer.start()
        self.tray=QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown),self);menu=QMenu();show=menu.addAction('YTDownPC 열기');show.triggered.connect(self.reveal);exit=menu.addAction('종료');exit.triggered.connect(self.exit_app);self.tray.setContextMenu(menu);self.tray.activated.connect(lambda reason:self.reveal());self.tray.show()
        for site in SITES:self.sessions.profile(site)
    @staticmethod
    def button(layout,text,call):
        b=QPushButton(text);b.clicked.connect(call);layout.addWidget(b);return b
    def options(self):return dict(output=str(Path(self.output.text()).expanduser().resolve()),quality=QUALITY_LABELS[self.quality.currentText()],audio_only=self.audio.isChecked(),immediate=self.immediate.isChecked(),wifi_only=self.wifi.isChecked(),https_assist=self.assist.isChecked(),auto_update=self.auto_update.isChecked(),cookies=self.sessions.snapshot())
    def persist(self,*args):save_settings(self.options())
    def error(self,e):QMessageBox.warning(self,'YTDownPC',redact(str(e)))
    def add_log(self,text):
        self.logs.append(time.strftime('%H:%M:%S')+' '+redact(text));self.logs=self.logs[-200:];self.log.setPlainText('\n'.join(self.logs))
    def enqueue(self):
        try:
            self.manager.enqueue(self.url.text(),self.options());self.persist();self.status.setText('대기열에 등록했습니다.');self.refresh()
        except Exception as e:self.error(e)
    def paste(self):
        self.url.setText(QApplication.clipboard().text().strip())
        if self.immediate.isChecked():self.enqueue()
    def dragEnterEvent(self,e):
        if e.mimeData().hasText():e.acceptProposedAction()
    def dropEvent(self,e):
        self.url.setText(e.mimeData().text().strip());e.acceptProposedAction()
        if self.immediate.isChecked():self.enqueue()
    def folder(self):
        if p:=QFileDialog.getExistingDirectory(self,'저장 폴더',self.output.text()):self.output.setText(p);self.persist()
    def open_folder(self):
        p=Path(self.output.text()).expanduser();p.mkdir(parents=True,exist_ok=True);QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
    def open_browser(self,site,url,**kw):
        w=BrowserWindow(self.sessions,site,url,parent=self,**kw);self.windows.append(w);w.destroyed.connect(lambda:self.windows.remove(w) if w in self.windows else None);w.show();return w
    def login(self):self.open_browser(self.site.currentText(),SITES[self.site.currentText()])
    def webpage(self):
        try:
            url=validate_web_url(self.url.text());host=urlsplit(url).hostname;site=next((s for s,u in SITES.items() if host.endswith(urlsplit(u).hostname.removeprefix('www.'))),'Web');self.open_browser(site,url)
        except Exception as e:self.error(e)
    def clear_login(self):
        site=self.site.currentText()
        if self.manager.busy():self.error('작업 중에는 로그인 정보를 지울 수 없습니다.');return
        if QMessageBox.question(self,'로그인 삭제',site+'의 앱 전용 로그인 쿠키를 지울까요?')==QMessageBox.StandardButton.Yes:self.sessions.clear(site);self.status.setText(site+' 로그인 쿠키 삭제 요청 완료')
    def account(self):
        try:
            url=validate_media_url(self.url.text());opts=self.options();reservation=self.manager.enqueue(url,opts,reserve=True)
            try:site,name,target=account_url(url);self.begin_scan(reservation,target)
            except ValueError:
                if 'instagram.com' not in urlsplit(url).hostname:raise
                self.status.setText('Instagram 게시물 작성자를 확인하는 중')
                def resolve():
                    try:
                        info=probe_video(url,opts['cookies']);owner=info.get('channel') or info.get('uploader_id')
                        if not owner:raise ValueError('게시물 작성자를 확인하지 못했습니다. 프로필 주소를 입력해 주세요.')
                        target='https://www.instagram.com/'+owner+'/';account_url(target);self.signals.event.emit(dict(stage='resolved-account',id=reservation,target=target))
                    except Exception as e:self.signals.event.emit(dict(stage='account-error',id=reservation,text=redact(str(e))))
                threading.Thread(target=resolve,daemon=True).start()
        except Exception as e:
            if 'reservation' in locals():self.manager.cancel(reservation)
            self.error(e)
    def begin_scan(self,id,target):
        site,name,target=account_url(target);w=self.open_browser(site,target,scan=True)
        w.job_id=id
        w.discovered.connect(lambda name,links:self.manager.resolve(id,links,name,self.sessions.snapshot()))
        w.scanFailed.connect(lambda text:self.apply_event(dict(stage='account-error',id=id,text=text)));self.add_log('계정 검색 창에서 로그인 후 계정 검색 시작을 눌러 주세요.')
    def cancel_all(self):
        now=time.monotonic()
        if now-self.last_cancel<=1:self.manager.cancel();self.status.setText('현재 작업과 대기열 취소 요청 완료');self.last_cancel=0
        else:self.last_cancel=now;self.status.setText('1초 안에 한 번 더 누르면 현재 작업과 대기열을 취소합니다.')
    def cancel_selected(self):
        item=self.queue_list.currentItem()
        if item:self.manager.cancel(item.data(Qt.ItemDataRole.UserRole))
    def incomplete(self):
        try:
            if self.manager.busy():raise RuntimeError('계정 검색·실행·대기 작업이 있을 때는 파일 정리를 할 수 없습니다.')
            from PySide6.QtWidgets import QDialog,QListWidgetItem
            rows=partial_files(self.output.text());dialog=QDialog(self);dialog.setWindowTitle('미완료 파일 · 완료 파일은 제외');dialog.resize(760,430);box=QVBoxLayout(dialog);listing=QListWidget();box.addWidget(listing)
            for row in rows:
                item=QListWidgetItem(f"{Path(row['path']).name} | {format_bytes(row['bytes'])} | {time.strftime('%Y-%m-%d %H:%M',time.localtime(row['mtime_ns']/1e9))}");item.setData(Qt.ItemDataRole.UserRole,row);listing.addItem(item)
            box.addWidget(QLabel(str(Path(self.output.text())/'.ytdownpc-parts')))
            def remove(all=False):
                chosen=rows if all else [listing.currentItem().data(Qt.ItemDataRole.UserRole)] if listing.currentItem() else []
                if not chosen:return
                if QMessageBox.question(dialog,'영구 삭제',f'{len(chosen)}개 임시 파일을 삭제할까요? 이어받기 데이터가 사라집니다.')!=QMessageBox.StandardButton.Yes:return
                try:
                    n=self.manager.cleanup(self.output.text(),chosen);self.status.setText(f'{n}개 삭제, {len(chosen)-n}개 변경/건너뜀');dialog.accept()
                except Exception as e:self.error(e)
            self.button(box,'선택 파일 삭제',remove);self.button(box,'목록 전체 삭제',lambda:remove(True));dialog.exec()
        except Exception as e:self.error(e)
    def update(self):
        if self.manager.busy():self.error('실행·대기 작업 완료 후 업데이트해 주세요.');return
        def work():
            try:r=update_library(True);self.signals.event.emit(dict(stage='message',text='라이브러리 '+r['version']+' 확인 완료 · 다음 작업부터 적용'))
            except Exception as e:self.signals.event.emit(dict(stage='message',text='업데이트 실패: '+redact(str(e))))
        threading.Thread(target=work,daemon=True).start();self.status.setText('공식 최신 stable 라이브러리 확인 중')
    def apply_event(self,e):
        stage=e.get('stage')
        if stage=='resolved-account':
            if any(j['id']==e['id'] and j['status']=='discovering' for j in self.manager.snapshot()):self.begin_scan(e['id'],e['target'])
        elif stage=='account-error':self.manager.cancel(e['id']);self.add_log(e['text']);self.status.setText(e['text'])
        elif stage=='message':self.add_log(e.get('text',''));self.status.setText(e.get('text',''))
        elif stage=='metadata':self.title.setText(e['title'])
        elif stage=='downloading':self.progress.setValue(int(e.get('percent') or 0));self.status.setText(f"저장 중 {e.get('percent',0):.0f}% · {format_bytes(e.get('downloaded'))} · {format_bytes(e.get('speed'))}/s")
        elif stage=='processing':self.progress.setValue(99);self.status.setText('병합·음원 추출·최종 파일 확인 중')
        elif stage=='preparing':self.progress.setValue(0);self.status.setText('미디어 정보 확인 중')
        self.refresh()
    def refresh(self):
        selected=self.queue_list.currentItem().data(Qt.ItemDataRole.UserRole) if self.queue_list.currentItem() else None
        self.queue_list.clear()
        from PySide6.QtWidgets import QListWidgetItem
        labels={'queued':'대기','waiting-wifi':'Wi-Fi 대기','discovering':'계정 검색 대기/진행','running':'실행','completed':'완료','failed':'실패/일부 실패','cancelled':'취소'}
        for j in self.manager.snapshot():
            if j['status']=='cancelled':
                for w in self.windows[:]:
                    if getattr(w,'job_id',None)==j['id']:w.close()
            name=j['account'] or j.get('result',{}).get('title') if j.get('result') else j['account'] or urlsplit(j['url']).path
            item=QListWidgetItem(f"{labels[j['status']]} · {name} · {j['completed_items']}/{j['total_items']} 완료 · {j['failed_items']} 실패")
            item.setData(Qt.ItemDataRole.UserRole,j['id']);self.queue_list.addItem(item)
            if j['id']==selected:self.queue_list.setCurrentItem(item)
            if j['status'] in {'completed','failed','cancelled'} and j['id'] not in self.seen_completed:
                self.seen_completed.add(j['id']);self.add_log(item.text()+((' · '+j['error']) if j['error'] else ''));self.status.setText(item.text())
                if j['status']=='completed':self.progress.setValue(100);self.title.setText((j['result'] or {}).get('title','미디어'))
        self.login_status.setText(' · '.join(s+(': 세션 있음' if self.sessions.ready(s) else ': 미저장') for s in SITES))
    def help(self):QMessageBox.information(self,'사용 방법','링크 입력 → 영상 화질 또는 M4A 선택 → 저장 폴더 → 다운로드.\n붙여넣기/드롭은 바로 다운로드 설정을 따릅니다.\n대기열에서 개별 취소, 전체 취소는 1초 안에 두 번 누릅니다.\n계정 전체는 프로필/게시물 작성자를 확인하고 검색 창에서 직접 로그인한 후 검색 시작을 누르세요. 끝 페이지 확인 실패 시 부분 목록을 전체로 처리하지 않습니다.\nWi-Fi 설정은 시작 시에만 적용됩니다. 진행 중 연결이 바뀌어도 중단하지 않습니다.\n로그인/보안 확인·CAPTCHA는 직접 처리해야 합니다. 인증서 오류를 무시하지 않습니다.\n창을 최소화해도 다운로드는 계속됩니다. 강제 종료 후 대기열 복원은 지원하지 않습니다.')
    def reveal(self):self.showNormal();self.raise_();self.activateWindow()
    def exit_app(self):self.manager.close();self.tray.hide();QApplication.quit()
    def closeEvent(self,event):
        if self.manager.busy() and QMessageBox.question(self,'백그라운드 처리','작업이 남아 있습니다. 창만 숨기고 백그라운드에서 계속할까요?\n아니요를 누르면 작업을 취소하고 종료합니다.')==QMessageBox.StandardButton.Yes:self.hide();event.ignore();return
        self.persist();self.manager.close()
        for w in self.windows[:]:w.close()
        self.tray.hide();event.accept()
def run():
    app=QApplication.instance() or QApplication([]);app.setApplicationName('YTDownPC');app.setOrganizationName('YTDownPC');app.setQuitOnLastWindowClosed(False)
    window=DownloaderApp();window.show();app.aboutToQuit.connect(window.manager.close);window.destroyed.connect(app.quit)
    # Closing the main window cancels work and exits; hiding it keeps the tray alive.
    original=window.closeEvent
    def closed(event):
        original(event)
        if event.isAccepted():app.quit()
    window.closeEvent=closed
    return app.exec()
