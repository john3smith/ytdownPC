import io,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import pc_engine as engine
import pc_storage as store
from pc_queue import DownloadQueue,ProcessTree
from pc_browser import account_url

class PolicyTests(unittest.TestCase):
    def test_accepted_hosts(self):
        for h in ['youtube.com','www.youtube.com','youtu.be','m.instagram.com','x.com','twitter.com']:
            self.assertEqual(engine.validate_media_url('https://'+h+'/a'),'https://'+h+'/a')
    def test_rejects_confused_urls(self):
        for u in ['file:///etc/passwd','https://x.com.evil.test/a','https://x.com@evil.test/a','https://user:pw@x.com/a','https://x.com:8080/a','https://localhost/a','javascript:alert(1)']:
            with self.subTest(u=u),self.assertRaises(ValueError):engine.validate_media_url(u)
    def test_web_https_only(self):
        for u in ['file:///a','http://example.com/','https://u:p@example.com/','data:text/plain,a']:
            with self.assertRaises(ValueError):engine.validate_web_url(u)
    def test_image_cdn_boundaries(self):
        self.assertTrue(engine.valid_image_url('https://pbs.twimg.com/media/a.jpg'))
        for u in ['https://evil-twimg.com/a','https://twimg.com.evil.test/a','http://pbs.twimg.com/a','https://127.0.0.1/a']:
            self.assertFalse(engine.valid_image_url(u))
    def test_redacts_diagnostics(self):
        s=engine.redact('https://x.com/a?token=example Cookie: example\nC:\\Users\\someone\\private.txt')
        self.assertNotIn('someone',s);self.assertNotIn('example',s)
    def test_account_urls(self):
        self.assertEqual(account_url('https://x.com/example/status/123')[2],'https://x.com/example/media')
        self.assertEqual(account_url('https://www.instagram.com/example/reels/')[1],'example')
        for u in ['https://youtube.com/a','https://www.instagram.com/p/abc/','https://x.com/home']:
            with self.assertRaises(ValueError):account_url(u)
class StorageTests(unittest.TestCase):
    def test_settings_recover_from_non_object_json(self):
        with tempfile.TemporaryDirectory() as td,patch.object(store,'DATA_DIR',Path(td)):
            path=Path(td)/'settings.json'
            for value in [None,[],42,'text',True]:
                path.write_text(json.dumps(value),encoding='utf-8')
                self.assertEqual(store.settings(),store.DEFAULTS)
                self.assertEqual(json.loads(path.read_text('utf-8')),value)
    def test_settings_keep_only_valid_known_values(self):
        with tempfile.TemporaryDirectory() as td,patch.object(store,'DATA_DIR',Path(td)):
            path=Path(td)/'settings.json'
            path.write_text(json.dumps(dict(output=None,quality=[],audio_only='false',immediate=0,wifi_only=True,unknown='ignored')),encoding='utf-8')
            actual=store.settings()
            self.assertEqual(actual,{**store.DEFAULTS,'wifi_only':True})
            valid={**store.DEFAULTS,'output':str(Path(td)/'한글'),'quality':'720','audio_only':True,'immediate':False}
            path.write_text(json.dumps(valid),encoding='utf-8')
            self.assertEqual(store.settings(),valid)
    def test_settings_reject_oversized_file(self):
        with tempfile.TemporaryDirectory() as td,patch.object(store,'DATA_DIR',Path(td)):
            (Path(td)/'settings.json').write_text(json.dumps({'output':'a'*65536}),encoding='utf-8')
            self.assertEqual(store.settings(),store.DEFAULTS)
    def test_settings_deep_json_does_not_crash_or_replace_source(self):
        with tempfile.TemporaryDirectory() as td,patch.object(store,'DATA_DIR',Path(td)):
            path=Path(td)/'settings.json';raw='['*2000+'0'+']'*2000
            path.write_text(raw,encoding='utf-8')
            self.assertEqual(store.settings(),store.DEFAULTS)
            self.assertEqual(path.read_text('utf-8'),raw)
    def test_runtime_activation_ignores_invalid_metadata(self):
        import sys
        with tempfile.TemporaryDirectory() as td,patch.object(store,'DATA_DIR',Path(td)):
            (Path(td)/'runtime').mkdir();(Path(td)/'runtime/yt-dlp.zip').write_bytes(b'bad')
            before=list(sys.path)
            for record in [None,[],42,{'sha256':[]},{'sha256':None}]:
                store.atomic_json(Path(td)/'library.json',record)
                store.activate_library()
                self.assertEqual(sys.path,before)
    def test_runtime_update_recovers_invalid_metadata_without_network(self):
        import hashlib,zipfile
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w') as archive:archive.writestr('yt_dlp/__init__.py','# synthetic test runtime')
        raw=payload.getvalue();checksum=hashlib.sha256(raw).hexdigest()
        prefix='https://github.com/yt-dlp/yt-dlp/releases/download/test/'
        release=json.dumps(dict(tag_name='test',assets=[dict(name=n,browser_download_url=prefix+n) for n in ['yt-dlp','SHA2-256SUMS']])).encode()
        def fetch(url):return release if url.endswith('/latest') else (checksum+'  yt-dlp\n').encode() if url.endswith('SHA2-256SUMS') else raw
        with tempfile.TemporaryDirectory() as td,patch.object(store,'DATA_DIR',Path(td)),patch.object(store,'_get',side_effect=fetch):
            for record in [None,[],42,{'checked':'yesterday'},{'checked':float('inf')},{'checked':10**1000},{'checked':time.time()+100000}]:
                store.atomic_json(Path(td)/'library.json',record)
                self.assertEqual(store._update_library()['sha256'],checksum)
                self.assertEqual((Path(td)/'runtime/yt-dlp.zip').read_bytes(),raw)
    def test_private_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'private.bin';data={'value':'test-only-placeholder'};store.write_private(p,data)
            self.assertNotIn(b'test-only-placeholder',p.read_bytes());self.assertEqual(store.read_private(p),data)
    def test_cleanup_is_conservative(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/'.ytdownpc-parts';base.mkdir()
            for n in ['a.part','b.part-Frag2','c.ytdl','done.mp4','unknown.jpg']:(base/n).write_bytes(b'test')
            (Path(td)/'outside.part').write_bytes(b'keep')
            rows=store.partial_files(td);self.assertEqual(len(rows),3)
            changed=rows[0];Path(changed['path']).write_bytes(b'changed')
            self.assertFalse(store.delete_partial(td,changed))
            for r in rows[1:]:self.assertTrue(store.delete_partial(td,r))
            self.assertTrue((base/'done.mp4').exists());self.assertTrue((Path(td)/'outside.part').exists())
    def test_output_crossprocess_exclusion(self):
        with tempfile.TemporaryDirectory() as td:
            with store.OutputLock(td):
                with self.assertRaises(RuntimeError):
                    with store.OutputLock(td):pass
    def test_modified_update_rejected_on_activation(self):
        with tempfile.TemporaryDirectory() as td,patch.object(store,'DATA_DIR',Path(td)):
            (Path(td)/'runtime').mkdir();(Path(td)/'runtime/yt-dlp.zip').write_bytes(b'bad')
            store.atomic_json(Path(td)/'library.json',dict(sha256='0'*64))
            import sys
            before=list(sys.path);store.activate_library();self.assertEqual(before,sys.path)
class SocialTests(unittest.TestCase):
    def test_twitter_photo_only_raw(self):
        ie=engine.TwitterPhotosIE()
        with patch.object(ie,'_extract_status',return_value={'extended_entities':{'media':[dict(type='photo',media_url_https='https://pbs.twimg.com/media/a.jpg')]}}):
            d=ie._real_extract('https://x.com/example/status/123')
        self.assertEqual(len(d['entries']),1);self.assertIn('name=orig',d['entries'][0]['_ytdown_photo'])
    def test_instagram_best_original_size(self):
        ie=engine.InstagramPhotosIE();d=ie._extract_product_media(dict(pk='1',image_versions2=dict(candidates=[dict(width=10,height=10,url='small'),dict(width=100,height=100,url='large')])))
        self.assertEqual(d['_ytdown_photo'],'large')
    def test_photo_bytes_verified(self):
        from PIL import Image
        data=io.BytesIO();Image.new('RGB',(16,9),'red').save(data,format='JPEG');payload=data.getvalue()
        class Response(io.BytesIO):
            url='https://pbs.twimg.com/media/test.jpg';headers={'Content-Length':str(len(payload))}
        class Ydl:
            def urlopen(self,request):return Response(payload)
        with tempfile.TemporaryDirectory() as td:
            output=Path(td);temp=output/'.ytdownpc-parts';temp.mkdir();p=engine.download_photo(Ydl(),engine.photo_info(Response.url,'1','사진'),output,temp,lambda e:None)
            self.assertEqual(p.read_bytes(),payload);self.assertFalse(list(temp.glob('*.part')))
class QueueTests(unittest.TestCase):
    def wait(self,fn,limit=3):
        start=time.monotonic()
        while not fn():
            if time.monotonic()-start>limit:self.fail('condition timeout')
            time.sleep(.01)
    def test_snapshot_wifi_and_cancel(self):
        q=DownloadQueue(network=lambda:False)
        try:
            opts=dict(output='unused',quality='720',wifi_only=True,audio_only=True)
            id=q.enqueue('https://youtu.be/a',opts);opts['quality']='best'
            self.wait(lambda:q.snapshot()[0]['status']=='waiting-wifi');self.assertEqual(q.jobs[0]['options']['quality'],'720')
            with self.assertRaises(RuntimeError):q.cleanup('unused',[])
            q.cancel(id);self.assertEqual(q.snapshot()[0]['status'],'cancelled')
        finally:q.close()
    def test_discovery_reservation_blocks_following_job(self):
        q=DownloadQueue();calls=[]
        q._run_item=lambda j,u:(calls.append(u) or dict(files=['file'],title='test'))
        try:
            first=q.enqueue('https://x.com/example',{},reserve=True);second=q.enqueue('https://youtu.be/a',{})
            time.sleep(.4);self.assertFalse(calls)
            q.resolve(first,['https://x.com/example/status/1'],'example',[])
            self.wait(lambda:all(j['status']=='completed' for j in q.snapshot()))
            self.assertEqual(calls,['https://x.com/example/status/1','https://youtu.be/a'])
        finally:q.close()
    def test_partial_account_failure_continues_next_job(self):
        q=DownloadQueue();calls=[]
        def run(j,u):
            calls.append(u)
            if u.endswith('/1'):raise RuntimeError('test failure')
            return dict(files=['file'],title='test')
        q._run_item=run
        try:
            q.enqueue('https://x.com/example',{},links=['https://x.com/example/status/1','https://x.com/example/status/2'])
            q.enqueue('https://youtu.be/a',{})
            self.wait(lambda:all(j['status'] in ['completed','failed'] for j in q.snapshot()))
            self.assertEqual([j['status'] for j in q.snapshot()],['failed','completed']);self.assertEqual(q.snapshot()[0]['failed_items'],1)
        finally:q.close()
    def test_cancel_kills_child_process_tree(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as td:
            pidfile=Path(td)/'pid.txt'
            code='import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(60)'
            tree=ProcessTree([sys.executable,'-c',code,str(pidfile)])
            try:self.wait(lambda:pidfile.exists() and pidfile.stat().st_size>0);pid=int(pidfile.read_text());tree.close();tree.wait()
            finally:tree.close();tree.wait()
            import win32api,win32con,win32event
            try:
                h=win32api.OpenProcess(win32con.SYNCHRONIZE,False,pid)
                try:self.assertEqual(win32event.WaitForSingleObject(h,3000),win32event.WAIT_OBJECT_0)
                finally:h.Close()
            except Exception as e:
                if getattr(e,'winerror',None)!=87:raise
if __name__=='__main__':unittest.main()
