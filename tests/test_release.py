"""Release identity, allowlisted artifacts, worker upgrades and legacy-data retention."""
import functools
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from playwright.sync_api import expect

from browser_support import BrowserTestCase, QuietHandler, ROOT

sys.path.insert(0, str(ROOT / 'scripts'))
from build_site import build
from check_static import check
from verify_deployment import verify


class ArtifactTests(unittest.TestCase):
    def test_syntax_and_exact_publication_identity(self):
        check()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'site'
            commit = 'a' * 40
            build(output, commit)
            self.assertEqual({p.name for p in output.iterdir()}, {
                'index.html', 'sw.js', 'manifest.webmanifest', 'version.json', '.nojekyll',
            })
            check(output)
            server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=temporary))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}/site/'
                self.assertEqual(verify(url, commit)['commit'], commit)
                with self.assertRaisesRegex(ValueError, 'revision differs'):
                    verify(url, 'b' * 40)
                with (output / 'index.html').open('a') as stream:
                    stream.write('<!-- stale/mixed deployment -->')
                with self.assertRaisesRegex(ValueError, 'differs'):
                    verify(url, commit)
                (output / 'private-photo.jpg').write_bytes(b'never publish')
                with self.assertRaisesRegex(ValueError, 'unexpected files'):
                    build(output, commit)
            finally:
                server.shutdown()
                server.server_close()

    def test_build_refuses_checkout_and_invalid_commit(self):
        with self.assertRaises(ValueError):
            build(ROOT, 'a' * 40)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                build(temporary, 'main')

    def test_build_rejects_symlinks_without_overwriting_user_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'user.html'
            target.write_text('preserve user file')
            output = root / 'site'
            output.mkdir()
            (output / 'index.html').symlink_to(target)
            with self.assertRaises(ValueError):
                build(output, 'a' * 40)
            self.assertEqual(target.read_text(), 'preserve user file')
            link = root / 'linked-directory'
            link.symlink_to(output, target_is_directory=True)
            with self.assertRaises(ValueError):
                build(link, 'a' * 40)


class UpgradeTests(BrowserTestCase):
    def test_existing_database_and_worker_update_preserve_user_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'site'
            old, new = 'a' * 40, 'b' * 40
            build(output, old)
            # SimpleHTTPRequestHandler validates at one-second precision. Give
            # the old release a distinct mtime so same-size SHA markers cannot
            # falsely return 304 when both test releases are built in one second.
            for item in output.iterdir():
                os.utime(item, (1, 1))
            # Separate empty page allows seeding the real pre-v18 DB before app opens v2.
            (Path(temporary) / 'setup.html').write_text('<title>Seed legacy test data</title>')
            server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=temporary))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                origin = f'http://127.0.0.1:{server.server_port}'
                self.page.goto(origin + '/setup.html')
                self.page.evaluate('''async () => {
                    localStorage.setItem('hooplog_training_sessions_v15', JSON.stringify([
                      {date:'2026-01-01',rounds:10,left:4,right:6,seconds:60}
                    ]));
                    const db = await new Promise((ok,bad) => {
                      const r=indexedDB.open('hooplog-offline-v1',1);
                      r.onupgradeneeded=()=>{
                        r.result.createObjectStore('folders',{keyPath:'id'});
                        r.result.createObjectStore('videos',{keyPath:'id'}).createIndex('folderId','folderId');
                      };
                      r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error);
                    });
                    await new Promise((ok,bad)=>{
                      const tx=db.transaction(['folders','videos'],'readwrite');
                      tx.objectStore('folders').put({id:'legacy-folder',name:'20260101 legacy',
                        files:[{id:'legacy-video',name:'old.mp4',kind:'video',modifiedTime:'original'}],
                        records:[{clip:'old.mp4',action:'原地投篮',result:'成功',note:'keep'}], savedAt:1});
                      tx.objectStore('videos').put({id:'legacy-video',folderId:'legacy-folder',
                        modifiedTime:'original',size:4,blob:new Blob([new Uint8Array([1,2,3,4])],{type:'video/mp4'})});
                      tx.oncomplete=ok;tx.onerror=()=>bad(tx.error);
                    }); db.close();
                    const unrelated=await caches.open('unrelated-application-cache');
                    await unrelated.put('/sentinel',new Response('keep'));
                }''')
                self.page.goto(origin + '/site/')
                expect(self.page.locator('[data-pick="legacy-folder"]')).to_be_visible()
                self.page.evaluate("async()=>{await navigator.serviceWorker.register('./sw.js');await navigator.serviceWorker.ready}")
                self.page.wait_for_function('navigator.serviceWorker.controller !== null')
                build(output, new)
                self.page.reload()
                expect(self.page.locator('meta[name="hooplog-build"]')).to_have_attribute('content', new)
                self.page.evaluate("async()=>{const r=await navigator.serviceWorker.getRegistration();await r.update()}")
                self.page.wait_for_function('''async (sha) => {
                    const keys=await caches.keys();
                    return keys.includes('hooplog-shell-v18-'+sha) && !keys.includes('hooplog-shell-v18-''' + old + "'); }", arg=new)
                self.context.set_offline(True)
                self.page.reload()
                expect(self.page.locator('meta[name="hooplog-build"]')).to_have_attribute('content', new)
                expect(self.page.locator('[data-pick="legacy-folder"]')).to_be_visible()
                result = self.page.evaluate('''async () => {
                    const db=await new Promise((ok,bad)=>{const r=indexedDB.open('hooplog-offline-v1');r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error)});
                    const get=(store,id)=>new Promise((ok,bad)=>{const r=db.transaction(store).objectStore(store).get(id);r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error)});
                    const video=await get('videos','legacy-video');const folder=await get('folders','legacy-folder');
                    const result={version:db.version,stores:Array.from(db.objectStoreNames),
                      bytes:Array.from(new Uint8Array(await video.blob.arrayBuffer())),
                      note:folder.records[0].note,history:JSON.parse(localStorage.getItem('hooplog_training_sessions_v15')),
                      unrelated:await caches.has('unrelated-application-cache')}; db.close();return result;
                }''')
                self.assertEqual(result['version'], 2)
                self.assertEqual(set(result['stores']), {'videos', 'folders', 'adventure_media'})
                self.assertEqual(result['bytes'], [1, 2, 3, 4])
                self.assertEqual(result['note'], 'keep')
                self.assertEqual(result['history'][0]['rounds'], 10)
                self.assertTrue(result['unrelated'])
                self.context.set_offline(False)
            finally:
                server.shutdown()
                server.server_close()
