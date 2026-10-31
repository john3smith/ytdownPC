"""Offline Qt UI checks; no personal profiles, clipboard or network are used."""
import os
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from PySide6.QtCore import QObject,Signal,Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton,QCheckBox
import pc_gui
import pc_browser
from pc_storage import DEFAULTS


class Clipboard(QObject):
    dataChanged=Signal()
    value=''
    def text(self):return self.value


class Sessions:
    def __init__(self,parent):pass
    def profile(self,site):pass
    def snapshot(self):return []
    def user_agent(self,url):return None
    def ready(self,site):return False


class DesktopParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.clipboard=Clipboard()
        self.patches=[patch.object(pc_gui,'Sessions',Sessions),patch.object(pc_gui,'settings',return_value={**DEFAULTS,'immediate':False,'auto_update':False}),
                      patch.object(pc_gui,'save_settings'),patch.object(QApplication,'clipboard',return_value=self.clipboard)]
        for p in self.patches:p.start()
        self.window=pc_gui.DownloaderApp();self.window.show();self.window.activateWindow();QTest.qWait(250)

    def tearDown(self):
        self.window.close();self.window.manager.thread.join(2);self.window.deleteLater();self.app.processEvents()
        for p in reversed(self.patches):p.stop()

    def test_clipboard_toggle_dedup_and_explicit_paste(self):
        w=self.window
        with patch.object(w.manager,'enqueue',return_value='test-job') as enqueue,patch.object(QApplication,'activeWindow',return_value=w):
            self.clipboard.value='설명 https://youtu.be/ownedfixture'
            w.clipboard_changed();self.assertEqual(w.url.text(),'https://youtu.be/ownedfixture');enqueue.assert_not_called()
            w.immediate.setChecked(True);w.clipboard_changed();w.clipboard_changed();self.assertEqual(enqueue.call_count,1)
            # Focus changes do not undo an edit to the input or repeat a download.
            w.url.setText('https://youtu.be/manual');w.clipboard_changed();self.assertEqual(w.url.text(),'https://youtu.be/manual')
            w.paste();self.assertEqual(enqueue.call_count,2)
            w.immediate.setChecked(False);w.receive_link('사진 https://instagr.am/p/fixture/');self.assertEqual(enqueue.call_count,2)

    def test_collapsible_options_short_window_and_enlarged_text(self):
        w=self.window;self.assertFalse(w.options_panel.isVisible())
        capture=Path(os.environ.get('YTDOWNPC_UI_CAPTURE','verification/ui'));capture.mkdir(parents=True,exist_ok=True)
        w.grab().save(str(capture/'normal.png'))
        QTest.mouseClick(w.options_button,Qt.MouseButton.LeftButton);self.assertTrue(w.options_panel.isVisible())
        w.audio.setChecked(True);self.assertFalse(w.quality.isEnabled())
        QTest.qWait(150)
        w.grab().save(str(capture/'options.png'))
        w.resize(640,480);w.setStyleSheet(w.styleSheet().replace('10pt','13pt'));QTest.qWait(200)
        scroll=w.download_scroll
        for control in scroll.widget().findChildren(QPushButton)+scroll.widget().findChildren(QCheckBox):
            if not control.isVisible():continue
            scroll.ensureWidgetVisible(control,0,0);self.app.processEvents()
            self.assertGreaterEqual(control.width(),control.minimumSizeHint().width(),control.text())
            top=control.mapTo(scroll.viewport(),QPoint(0,0));bottom=control.mapTo(scroll.viewport(),control.rect().bottomRight())
            self.assertGreaterEqual(top.x(),0,control.text());self.assertLess(bottom.x(),scroll.viewport().width(),control.text())
            self.assertGreaterEqual(top.y(),0,control.text());self.assertLess(bottom.y(),scroll.viewport().height(),control.text())
        w.grab().save(str(capture/'short-large-text.png'))
        w.tabs.setCurrentIndex(2);self.app.processEvents();w.grab().save(str(capture/'account.png'))

    def test_page_readiness_requires_load_delay_and_trusted_page(self):
        w=Mock();w.view.url.return_value.toString.return_value='https://www.pornhub.com/view_video.php?viewkey=fixture'
        w.trusted_session_page=lambda:pc_browser.BrowserWindow.trusted_session_page(w)
        w.refresh_session=lambda:pc_browser.BrowserWindow.refresh_session(w)
        w.site='추가 사이트';sessions=Mock();sessions.confirmed=set()
        with patch.object(pc_browser.time,'monotonic',return_value=10):
            pc_browser.BrowserWindow.loaded_session(w,True);self.assertEqual(w.ready_at,13)
            pc_browser.BrowserWindow.confirm_session(w,sessions);self.assertFalse(sessions.confirmed)
        with patch.object(pc_browser.time,'monotonic',return_value=13):
            pc_browser.BrowserWindow.confirm_session(w,sessions);self.assertIn('추가 사이트',sessions.confirmed)
        pc_browser.BrowserWindow.invalidate_session(w);self.assertEqual(w.ready_at,float('inf'))
        w.view.url.return_value.toString.return_value='https://pornhub.com.evil.test/'
        self.assertFalse(w.trusted_session_page())


if __name__=='__main__':unittest.main()
