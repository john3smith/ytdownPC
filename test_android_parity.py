"""Desktop parity checks with generated, owned media and a loopback-only server."""
import functools
import hashlib
import http.server
import datetime
import ipaddress
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import yt_dlp
from yt_dlp.extractor.common import InfoExtractor
import pc_engine as engine
from pc_parity import StreamProgress, extract_media_url, failure_advice
from pc_storage import ffmpeg_path


class ParityPolicyTests(unittest.TestCase):
    def test_additional_video_urls_normalized(self):
        expected='https://www.pornhub.com/view_video.php?viewkey=ph123'
        for link in ['http://www.pornhub.com/embed/ph123/', 'https://de.pornhub.com/video/show?x=1&viewkey=ph123',expected+'&tracking=ignore']:
            self.assertEqual(engine.validate_media_url(link),expected)
        for link in ['https://www.pornhub.com/',expected+'&viewkey=other','https://pornhub.com.evil.test/embed/ph123','https://user@pornhub.com/embed/ph123','https://pornhub.com:8080/embed/ph123']:
            with self.subTest(link=link),self.assertRaises(ValueError):engine.validate_media_url(link)

    def test_text_links_and_android_aliases(self):
        self.assertEqual(extract_media_url('게시물 설명\nhttps://www.youtube-nocookie.com/embed/abc'), 'https://www.youtube-nocookie.com/embed/abc')
        self.assertEqual(extract_media_url('사진: https://instagr.am/p/abc/'), 'https://instagr.am/p/abc/')
        self.assertIsNone(extract_media_url('https://x.com.evil.test/a https://user:password@x.com/a'))

    def test_stream_progress_reserves_100_and_handles_unknown_duration(self):
        progress=StreamProgress(20)
        progress.accept('out_time_ms=10000000')
        progress.accept('total_size=1024')
        self.assertEqual(progress.accept('progress=continue')['percent'],50)
        progress.accept('out_time_us=21000000')
        self.assertEqual(progress.accept('progress=end')['percent'],99)
        self.assertEqual(StreamProgress(float('nan')).accept('progress=end')['percent'],None)
        self.assertEqual(StreamProgress(20,True).accept('progress=end')['percent'],None)
        fresh=StreamProgress(10)
        fresh.accept('out_time_us=-123')
        self.assertEqual(fresh.accept('progress=end')['elapsed'],0)

    def test_diagnostics_explain_known_errors(self):
        for value in ['certificate verify failed','HTTP Error 403','HTTP Error 404','WinError 10054','Timeout','ffmpeg exited with code 1']:
            self.assertIsNotNone(failure_advice(value))
        self.assertIsNone(failure_advice('unknown failure'))


class OwnedMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory();cls.root=Path(cls.folder.name);cls.ffmpeg=ffmpeg_path()
        cls.source=cls.root/'fixture.mp4'
        subprocess.run([cls.ffmpeg,'-nostdin','-v','error','-f','lavfi','-i','testsrc=size=160x90:rate=12',
                        '-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(cls.source)],
                       check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=30)
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(cls.root)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.media_url=f'http://127.0.0.1:{cls.server.server_port}/fixture.mp4'
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes,serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'YTDownPC loopback fixture')])
        now=datetime.datetime.now(datetime.timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1))
              .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
              .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256()))
        cls.ca=cls.root/'ca.pem';cls.ca.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        keyfile=cls.root/'key.pem';keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        cls.tls=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(cls.root)))
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(str(cls.ca),str(keyfile));cls.tls.socket=context.wrap_socket(cls.tls.socket,server_side=True)
        cls.tls_thread=threading.Thread(target=cls.tls.serve_forever,daemon=True);cls.tls_thread.start()
        cls.tls_url=f'https://127.0.0.1:{cls.tls.server_port}/fixture.mp4'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tls.shutdown();cls.tls.server_close();cls.tls_thread.join();cls.folder.cleanup()

    def test_real_download_audio_and_stream_pipeline(self):
        media_url=self.media_url;tls_url=self.tls_url
        class OwnedFixtureIE(InfoExtractor):
            _VALID_URL=r'https://(?:youtu\.be/ownedfixture|www\.pornhub\.com/view_video\.php\?viewkey=ownedfixture)'
            IE_NAME='owned-fixture'
            def _real_extract(self,url):
                return dict(id='ownedfixture',title='Owned synthetic fixture',duration=2,
                            formats=[dict(format_id='fixture',url=tls_url if 'pornhub.com' in url else media_url,ext='mp4',height=90,vcodec='h264',acodec='aac')])
        def factory(options,cookies=None):
            if options.get('external_downloader'):
                options['external_downloader_args']['ffmpeg_i'].append('-re')
            ydl=yt_dlp.YoutubeDL(options,auto_init=False)
            ydl.add_info_extractor(OwnedFixtureIE(ydl))
            return ydl
        with tempfile.TemporaryDirectory() as td,patch.object(engine,'create_ydl',side_effect=factory),patch('certifi.where',return_value=str(self.ca)):
            for kind,url,audio in [('video','https://youtu.be/ownedfixture',False),('audio','https://youtu.be/ownedfixture',True),('stream','https://www.pornhub.com/view_video.php?viewkey=ownedfixture',False)]:
                events=[];result=engine.download_video(url,Path(td)/kind,progress=events.append,audio_only=audio)
                self.assertTrue(result['files']);self.assertEqual(events[-1]['stage'],'complete')
                artifact=result['artifacts'][0];self.assertEqual(artifact['kind'],'audio' if audio else 'video')
                self.assertEqual(artifact['sha256'],hashlib.sha256(Path(result['file']).read_bytes()).hexdigest())
                self.assertFalse(list((Path(td)/kind/'.ytdownpc-parts').glob('*.progress')))
                if kind=='stream':self.assertTrue(any(e['stage']=='streaming' for e in events))
                # Re-request validates the existing exact output as well.
                again=engine.download_video(url,Path(td)/kind,audio_only=audio)
                self.assertEqual(again['artifacts'][0]['sha256'],artifact['sha256'])

    def test_invalid_or_wrong_media_never_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'bad.mp4';path.write_text('not media',encoding='utf-8')
            with self.assertRaises(ValueError):engine.verify_media(path,self.ffmpeg)
            audio=Path(td)/'silent.m4a'
            subprocess.run([self.ffmpeg,'-nostdin','-v','error','-i',str(self.source),'-vn','-c:a','copy',str(audio)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
            with self.assertRaises(ValueError):engine.verify_media(audio,self.ffmpeg)
            self.assertEqual(engine.verify_media(audio,self.ffmpeg,audio_only=True)['kind'],'audio')


if __name__=='__main__':unittest.main()
