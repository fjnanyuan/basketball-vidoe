"""Real-browser adventure regressions; Google Identity/Drive are simulated here.

These tests never authenticate a real account and cannot validate real OAuth,
Drive permissions, or Safari on an actual iPhone.
"""
import json
import re
import struct
import zlib
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect

from browser_support import BrowserTestCase, ROOT


DATA_KEY = 'hooplog_adventure_v18_data'


def png(red, green, blue):
    """Generate a tiny non-private fixture, preserving its exact encoded bytes."""
    def chunk(kind, payload):
        return (struct.pack('!I', len(payload)) + kind + payload
                + struct.pack('!I', zlib.crc32(kind + payload) & 0xffffffff))
    pixels = b''.join(b'\0' + bytes((red, green, blue, 255)) * 2 for _ in range(2))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 2, 2, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


TEMPLATE = png(210, 100, 40)
PHOTO_ONE = png(20, 110, 210)
PHOTO_TWO = png(20, 190, 100)


class FakeDrive:
    """A browser-route fake for the API protocol, not evidence of real access."""
    def __init__(self):
        self.files = {}
        self.sessions = {}
        self.next_id = 0
        self.fail_next_image = None
        self.denied_parent = None
        self.hold_rating_manifest = False
        self.held_manifest = None
        self.uploaded = []
        self.requests = []
        self.unhandled = []

    def install(self, context):
        context.add_init_script("""
            window.__oauthScopes = [];
            window.google = {accounts: {oauth2: {
                initTokenClient: config => ({requestAccessToken: () => {
                    window.__oauthScopes.push(config.scope);
                    config.callback({access_token: 'synthetic-test-token', expires_in: 3600});
                }}),
                revoke: (token, callback) => callback()
            }}};
        """)
        context.route('https://www.googleapis.com/**', self.handle)
        # No live Google Identity request should ever be needed by this fake.
        context.route('https://accounts.google.com/**', lambda route: route.abort())

    def new_id(self):
        self.next_id += 1
        return f'fake-{self.next_id}'

    def handle(self, route):
        request = route.request
        parsed = urlparse(request.url)
        query = parse_qs(parsed.query)
        path = parsed.path
        method = request.method
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Methods': '*',
            'Access-Control-Expose-Headers': 'Location',
        }

        def respond(value=None, status=200, extra=None, body=None, content_type='application/json'):
            route.fulfill(status=status, headers={**headers, **(extra or {})},
                          content_type=content_type,
                          body=body if body is not None else json.dumps(value or {}))

        if method == 'OPTIONS':
            respond()
            return
        self.requests.append((method, request.url, request.headers.get('authorization')))
        if request.headers.get('authorization') != 'Bearer synthetic-test-token':
            self.unhandled.append(('missing synthetic authorization', method, request.url))
            respond({'error': {'message': 'Expected synthetic test authorization'}}, 401)
            return

        if path == '/drive/v3/files' and method == 'GET':
            q = query.get('q', [''])[0]
            match = re.search(r"^'(.+?)' in parents and name = '(.*?)' and trashed = false$", q)
            if not match:
                self.unhandled.append(('unexpected query', q))
                respond({'error': {'message': 'Unexpected test query'}}, 400)
                return
            parent, name = match.groups()
            name = name.replace("\\'", "'").replace('\\\\', '\\')
            if parent == self.denied_parent:
                respond({'error': {'message': 'Injected parent-folder permission denial'}}, 403)
                return
            respond({'files': [
                {k: f[k] for k in ('id', 'name', 'mimeType')}
                for f in self.files.values() if parent in f.get('parents', []) and f['name'] == name
            ]})
        elif path == '/drive/v3/files' and method == 'POST':
            metadata = request.post_data_json
            file_id = self.new_id()
            self.files[file_id] = {'id': file_id, **metadata}
            respond({'id': file_id})
        elif path.startswith('/drive/v3/files/') and method == 'GET':
            file_id = path.rsplit('/', 1)[1]
            file = self.files.get(file_id)
            if not file:
                respond({'error': {'message': 'Missing fake file'}}, 404)
            elif query.get('alt') == ['media']:
                respond(body=file['blob'], content_type=file['mimeType'])
            else:
                respond({k: file[k] for k in ('id', 'name', 'mimeType')})
        elif path == '/upload/drive/v3/files' and method == 'POST':
            session_id = self.new_id()
            self.sessions[session_id] = request.post_data_json
            respond(extra={'Location': f'https://www.googleapis.com/upload/test-session/{session_id}'})
        elif path.startswith('/upload/test-session/') and method == 'PUT':
            session_id = path.rsplit('/', 1)[1]
            metadata = self.sessions.pop(session_id)
            raw = request.post_data_buffer or b''
            if metadata['mimeType'].startswith('image/') and self.fail_next_image:
                failure = self.fail_next_image
                self.fail_next_image = None
                if failure == 'http':
                    respond({'error': {'message': 'Injected upload failure'}}, 503)
                else:
                    respond({'name': metadata['name']})  # No ID: must not show synced.
                return
            file_id = self.new_id()
            self.files[file_id] = {'id': file_id, **metadata, 'blob': raw}
            self.uploaded.append(file_id)
            respond({'id': file_id, 'name': metadata['name'], 'size': str(len(raw))})
        elif path.startswith('/upload/drive/v3/files/') and method == 'PATCH':
            file_id = path.rsplit('/', 1)[1]
            raw = request.post_data_buffer or b''
            metadata = json.loads(raw)
            if (self.hold_rating_manifest and metadata['shots']
                    and metadata['shots'][0]['rating'] == 'redo'):
                self.hold_rating_manifest = False
                self.held_manifest = (route, file_id, raw, headers)
                return
            self.files[file_id]['blob'] = raw
            respond({'id': file_id})
        else:
            self.unhandled.append((method, request.url))
            respond({'error': {'message': 'Unhandled fake Drive request'}}, 500)

    def release_manifest(self):
        route, file_id, raw, headers = self.held_manifest
        self.files[file_id]['blob'] = raw
        self.held_manifest = None
        route.fulfill(headers=headers, content_type='application/json', body=json.dumps({'id': file_id}))


class AdventureTests(BrowserTestCase):
    def open_app(self, page=None):
        page = page or self.page
        page.goto(self.base_url)
        expect(page.locator('#page .title')).to_have_text('训练文件夹')
        page.locator('[data-tab="adventure"]').click()
        expect(page.locator('.adv-title')).to_have_text('冒险 · 街拍姿势库')

    def view(self, name, page=None):
        (page or self.page).locator(f'[data-adv18="view"][data-view="{name}"]').first.click()

    def data(self, page=None):
        return (page or self.page).evaluate('(key) => JSON.parse(localStorage.getItem(key))', DATA_KEY)

    def customer(self, name, page=None):
        page = page or self.page
        self.view('customers', page)
        page.locator('[data-adv18="newcustomer"]').first.click()
        page.locator('#adv18-newcustomer-name').fill(name)
        page.locator('[data-adv18="saveCustomer"]').click()
        return self.data(page)['customers'][-1]['id']

    def upload_template(self, content=TEMPLATE, page=None):
        page = page or self.page
        self.view('gallery', page)
        page.locator('[data-adv18="addtemplate"]').click()
        page.locator('#adv18-template-name').fill('测试模板 A')
        page.locator('#adv18-template-tech').fill('低机位，侧转45°')
        page.locator('#adv18-template-note').fill('模板通用备注')
        with page.expect_file_chooser() as chooser:
            page.locator('[data-adv18="chooseTemplateFile"]').click()
        chooser.value.set_files({'name': 'template.png', 'mimeType': 'image/png', 'buffer': content})
        expect(page.locator('.adv-cardtitle')).to_have_text('测试模板 A')
        return self.data(page)['templates'][0]['id']

    def upload_photo(self, content, name='actual.png', page=None):
        page = page or self.page
        before = len(self.data(page)['shots'])
        with page.expect_file_chooser() as chooser:
            page.locator('[data-adv18="chooseShotFile"]').first.click()
        chooser.value.set_files({'name': name, 'mimeType': 'image/png', 'buffer': content})
        page.wait_for_function('(n) => JSON.parse(localStorage.hooplog_adventure_v18_data).shots.length === n', arg=before + 1)
        return self.data(page)['shots'][-1]['id']

    def media_bytes(self, page=None):
        return (page or self.page).evaluate('''async () => {
            const db = await new Promise((ok,bad) => {
                const r=indexedDB.open('hooplog-offline-v1',2);
                r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error);
            });
            const records=await new Promise((ok,bad) => {
                const r=db.transaction('adventure_media').objectStore('adventure_media').getAll();
                r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error);
            });
            const out=await Promise.all(records.map(async r => ({id:r.id,bytes:Array.from(new Uint8Array(await r.blob.arrayBuffer()))})));
            db.close();return out;
        }''')

    def connect(self, page=None):
        page = page or self.page
        # Public dummy OAuth client ID; this is not a credential or real account.
        page.locator('[data-tab="settings"]').click()
        page.locator('#clientId').fill('test-client.apps.googleusercontent.com')
        page.locator('#saveClient').click()
        page.locator('[data-tab="adventure"]').click()
        self.view('cloud', page)
        page.locator('[data-adv18="connect"]').click()
        expect(page.locator('#page')).to_contain_text('已同步到 Google Drive')

    def wait_synced(self, page=None):
        page = page or self.page
        page.wait_for_function("Array.from(document.querySelectorAll('.adv-banner,.adv-panel')).some(e => e.textContent.includes('已同步到 Google Drive'))")

    def test_local_customers_photos_history_and_original_bytes(self):
        self.open_app()
        a = self.customer('测试顾客 A')
        template = self.upload_template()
        self.page.locator('[data-adv18="togglePlan"]').click()
        self.view('plans')
        expect(self.page.locator('.adv-listitem')).to_have_count(1)
        self.page.locator('[data-adv18="openCompare"]').click()
        first = self.upload_photo(PHOTO_ONE, 'first.png')
        expect(self.page.locator('.adv-compare .adv-side')).to_have_count(2)
        self.page.wait_for_function("Array.from(document.querySelectorAll('.adv-compare img')).length===2 && Array.from(document.querySelectorAll('.adv-compare img')).every(i=>i.naturalWidth>0)")
        # Both panels remain side by side at the iPhone-sized test viewport.
        panels = self.page.locator('.adv-compare .adv-side').all()
        left, right = (panel.bounding_box() for panel in panels)
        self.assertLess(left['x'] + left['width'], right['x'] + 1)
        self.assertAlmostEqual(left['y'], right['y'], delta=1)
        self.page.locator('[data-adv18="rate"][data-rating="redo"]').click()
        self.page.locator('#adv18-shot-note').fill('顾客 A 专属评价：下次降低机位')
        self.page.locator('[data-adv18="saveShotNote"]').click()
        artifacts = ROOT / 'test-results'
        artifacts.mkdir(exist_ok=True)
        self.page.screenshot(path=str(artifacts / 'adventure-compare.png'), full_page=True)
        second = self.upload_photo(PHOTO_TWO, 'second.png')
        self.assertNotEqual(first, second)
        expect(self.page.locator('[data-adv18="pickShot"]')).to_have_count(2)
        self.page.locator(f'[data-adv18="pickShot"][data-id="{first}"]').click()
        expect(self.page.locator('#adv18-shot-note')).to_have_value('顾客 A 专属评价：下次降低机位')
        expect(self.page.locator('[data-adv18="rate"][data-rating="redo"]')).to_have_class('no')

        b = self.customer('测试顾客 B')
        self.assertNotEqual(a, b)
        self.view('compare')
        expect(self.page.locator('.adv-noimage')).to_be_visible()
        expect(self.page.locator('[data-adv18="pickShot"]')).to_have_count(0)
        expect(self.page.locator('#adv18-shot-note')).to_have_count(0)
        self.view('plans')
        expect(self.page.locator('.adv-listitem')).to_have_count(0)
        self.view('gallery')
        expect(self.page.locator('.adv-cardtitle')).to_have_text('测试模板 A')
        expect(self.page.locator('[data-adv18="togglePlan"]')).to_have_text('＋ 下次约拍')
        self.page.locator('[data-adv18="openCompare"]').click()
        self.page.locator('#adv18-customer').select_option(a)
        expect(self.page.locator('[data-adv18="pickShot"]')).to_have_count(2)
        self.page.reload()
        self.page.locator('[data-tab="adventure"]').click()
        self.view('compare')
        self.page.locator(f'[data-adv18="pickShot"][data-id="{first}"]').click()
        expect(self.page.locator('#adv18-shot-note')).to_have_value('顾客 A 专属评价：下次降低机位')
        data = self.data()
        self.assertEqual(len(data['shots']), 2)
        self.assertTrue(all(shot['customerId'] == a and shot['templateId'] == template for shot in data['shots']))
        self.assertTrue(all(not rec['driveId'] for rec in data['templates'] + data['shots']))
        encoded = sorted(bytes(row['bytes']) for row in self.media_bytes())
        self.assertEqual(encoded, sorted([TEMPLATE, PHOTO_ONE, PHOTO_TWO]))

    def test_deleted_plan_can_be_readded_and_rating_restores_it(self):
        self.open_app()
        self.customer('测试顾客 A')
        self.upload_template()
        button = self.page.locator('[data-adv18="togglePlan"]')
        button.click()
        expect(button).to_have_text('✓ 已选入')
        button.click()
        expect(button).to_have_text('＋ 下次约拍')
        self.assertTrue(self.data()['plans'][0]['deleted'])
        button.click()
        expect(button).to_have_text('✓ 已选入')
        self.assertFalse(self.data()['plans'][0]['deleted'])
        self.assertEqual(len(self.data()['plans']), 1)
        self.view('plans')
        expect(self.page.locator('.adv-listitem')).to_have_count(1)
        self.page.locator('[data-adv18="togglePlan"]').click()
        self.view('compare')
        self.upload_photo(PHOTO_ONE)
        self.page.locator('[data-adv18="rate"][data-rating="redo"]').click()
        self.assertFalse(self.data()['plans'][0]['deleted'])
        self.assertEqual(self.data()['plans'][0]['reason'], '上次不满意，安排重拍')
        self.view('plans')
        expect(self.page.locator('.adv-listitem')).to_have_count(1)
        self.page.reload()
        self.page.locator('[data-tab="adventure"]').click()
        self.view('plans')
        expect(self.page.locator('.adv-listitem')).to_have_count(1)

    def test_simulated_drive_upload_failure_retry_and_new_device_restore(self):
        drive = FakeDrive()
        drive.install(self.context)
        self.open_app()
        self.connect()
        self.assertEqual(self.page.evaluate('window.__oauthScopes'), ['https://www.googleapis.com/auth/drive.file'])
        a = self.customer('测试顾客 A')
        self.wait_synced()
        drive.fail_next_image = 'http'
        template = self.upload_template()
        expect(self.page.locator('.adv-banner')).to_contain_text('同步失败')
        self.assertEqual(self.data()['templates'][0]['driveId'], '')
        expect(self.page.locator('.adv-card .adv-caption')).to_have_text('待同步')
        self.assertEqual(bytes(self.media_bytes()[0]['bytes']), TEMPLATE)

        self.view('cloud')
        drive.fail_next_image = 'no-id'
        self.page.locator('[data-adv18="sync"]').click()
        expect(self.page.locator('#page')).to_contain_text('Google Drive 未返回文件 ID')
        self.assertEqual(self.data()['templates'][0]['driveId'], '')
        self.page.locator('[data-adv18="sync"]').click()
        self.page.wait_for_function("JSON.parse(localStorage.hooplog_adventure_v18_data).templates[0].driveId !== ''")
        self.wait_synced()
        self.view('gallery')
        expect(self.page.locator('.adv-card .adv-caption')).to_have_text('已同步')
        self.page.locator('[data-adv18="togglePlan"]').click()
        self.wait_synced()
        self.page.locator('[data-adv18="openCompare"]').click()
        shot = self.upload_photo(PHOTO_ONE, 'actual.png')
        self.page.wait_for_function("JSON.parse(localStorage.hooplog_adventure_v18_data).shots[0].driveId !== ''")
        self.wait_synced()
        with self.page.expect_response(lambda response:
                response.request.method == 'PATCH'
                and '"rating":"redo"' in (response.request.post_data or '')):
            self.page.locator('[data-adv18="rate"][data-rating="redo"]').click()
        self.wait_synced()
        self.page.locator('#adv18-shot-note').fill('云端测试评价')
        with self.page.expect_response(lambda response:
                response.request.method == 'PATCH'
                and '云端测试评价' in (response.request.post_data or '')):
            self.page.locator('[data-adv18="saveShotNote"]').click()
        self.wait_synced()
        source = self.data()
        template_file = drive.files[source['templates'][0]['driveId']]
        actual_file = drive.files[source['shots'][0]['driveId']]
        self.assertEqual(template_file['blob'], TEMPLATE)
        self.assertEqual(actual_file['blob'], PHOTO_ONE)
        self.assertEqual(drive.files[template_file['parents'][0]]['name'], '姿势模板')
        self.assertNotEqual(template_file['parents'], actual_file['parents'])
        actual_folder = drive.files[actual_file['parents'][0]]
        customer_folder = drive.files[actual_folder['parents'][0]]
        photo_root = drive.files[customer_folder['parents'][0]]
        self.assertTrue(actual_folder['name'].startswith('测试模板 A__'))
        self.assertTrue(customer_folder['name'].startswith('测试顾客 A__'))
        self.assertEqual(photo_root['name'], '顾客实拍')
        manifest = next(f for f in drive.files.values() if f['name'] == '冒险资料.json')
        remote = json.loads(manifest['blob'])
        self.assertEqual(remote['shots'][0]['note'], '云端测试评价')
        self.assertEqual(remote['shots'][0]['rating'], 'redo')

        # A separate browser context has no localStorage or IndexedDB from device A.
        restored_context = self.browser.new_context(viewport={'width': 390, 'height': 844})
        try:
            drive.install(restored_context)
            restored = restored_context.new_page()
            restored_errors = []
            restored.on('pageerror', lambda error: restored_errors.append(str(error)))
            self.open_app(restored)
            self.assertIsNone(self.data(restored))
            self.connect(restored)
            result = self.data(restored)
            self.assertEqual(result['customers'][0]['id'], a)
            self.assertEqual(result['templates'][0]['id'], template)
            self.assertEqual(result['shots'][0]['id'], shot)
            self.assertEqual(result['shots'][0]['rating'], 'redo')
            self.assertEqual(result['plans'][0]['customerId'], a)
            self.assertEqual(result['plans'][0]['templateId'], template)
            self.view('compare', restored)
            expect(restored.locator('#adv18-shot-note')).to_have_value('云端测试评价')
            restored.wait_for_function("Array.from(document.querySelectorAll('.adv-compare img')).length===2 && Array.from(document.querySelectorAll('.adv-compare img')).every(i=>i.naturalWidth>0)")
            self.assertEqual(sorted(bytes(row['bytes']) for row in self.media_bytes(restored)), sorted([TEMPLATE, PHOTO_ONE]))
            self.assertEqual(restored_errors, [])
        finally:
            restored_context.close()
        self.assertEqual(drive.unhandled, [])
        # Access tokens must never be serialized into application metadata/storage.
        all_storage = self.page.evaluate('JSON.stringify({...localStorage})')
        self.assertNotIn('synthetic-test-token', all_storage)

    def test_simulated_parent_permission_denial_keeps_local_photo(self):
        drive = FakeDrive()
        drive.denied_parent = 'existing-parent-id-123'
        drive.install(self.context)
        self.open_app()
        self.customer('测试顾客 A')
        self.upload_template()
        self.page.locator('[data-tab="settings"]').click()
        self.page.locator('#clientId').fill('test-client.apps.googleusercontent.com')
        self.page.locator('#saveClient').click()
        self.page.locator('[data-tab="adventure"]').click()
        self.view('cloud')
        self.page.locator('#adv18-parent').fill(drive.denied_parent)
        self.page.locator('[data-adv18="saveParent"]').click()
        self.page.locator('[data-adv18="connect"]').click()
        expect(self.page.locator('#page')).to_contain_text('没有权限写入这个已有文件夹')
        self.assertEqual(self.data()['templates'][0]['driveId'], '')
        self.assertEqual(bytes(self.media_bytes()[0]['bytes']), TEMPLATE)
        self.assertEqual(drive.uploaded, [])
        # Explicitly selecting the app-owned default is a supported recovery path.
        self.page.locator('#adv18-parent').fill('')
        self.page.locator('[data-adv18="saveParent"]').click()
        self.page.locator('[data-adv18="connect"]').click()
        self.page.wait_for_function("JSON.parse(localStorage.hooplog_adventure_v18_data).templates[0].driveId !== ''")
        self.wait_synced()
        self.assertEqual(drive.unhandled, [])

    def test_background_sync_preserves_unsaved_photo_note(self):
        drive = FakeDrive()
        drive.install(self.context)
        self.open_app()
        self.connect()
        self.customer('测试顾客 A')
        self.wait_synced()
        self.upload_template()
        self.page.wait_for_function("JSON.parse(localStorage.hooplog_adventure_v18_data).templates[0].driveId !== ''")
        self.wait_synced()
        self.page.locator('[data-adv18="openCompare"]').click()
        self.upload_photo(PHOTO_ONE)
        self.page.wait_for_function("JSON.parse(localStorage.hooplog_adventure_v18_data).shots[0].driveId !== ''")
        self.wait_synced()
        # Hold a real fetch response, then type while the app sync is pending.
        drive.hold_rating_manifest = True
        self.page.locator('[data-adv18="rate"][data-rating="redo"]').click()
        for _ in range(200):
            if drive.held_manifest is not None:
                break
            self.page.wait_for_timeout(10)
        self.assertIsNotNone(drive.held_manifest, 'Expected rating metadata request to be pending')
        note = self.page.locator('#adv18-shot-note')
        draft = '正在编辑，后台同步不能清空这段文字'
        note.fill(draft)
        note.evaluate('(element) => element.setSelectionRange(3, 7)')
        drive.release_manifest()
        self.wait_synced()
        expect(note).to_have_value(draft)
        expect(note).to_be_focused()
        self.assertEqual(note.evaluate('(element) => [element.selectionStart, element.selectionEnd]'), [3, 7])
        with self.page.expect_response(lambda response:
                response.request.method == 'PATCH' and draft in (response.request.post_data or '')):
            self.page.locator('[data-adv18="saveShotNote"]').click()
        self.assertEqual(self.data()['shots'][0]['note'], draft)

    def test_reconnect_shows_new_remote_note_when_saved_field_is_unchanged(self):
        drive = FakeDrive()
        drive.install(self.context)
        self.open_app()
        self.customer('测试顾客 A')
        self.upload_template()
        self.page.locator('[data-adv18="openCompare"]').click()
        self.upload_photo(PHOTO_ONE)
        old_note, new_note = '原来保存的评价', '另一设备保存的新评价'
        self.page.locator('#adv18-shot-note').fill(old_note)
        self.page.locator('[data-adv18="saveShotNote"]').click()

        # Simulate the same records edited more recently on another device.
        remote = self.data()
        for category in ('customers', 'templates', 'shots'):
            for record in remote[category]:
                record['updatedAt'] += 1
        remote['templates'][0]['driveId'] = 'remote-template'
        remote['shots'][0]['driveId'] = 'remote-photo'
        remote['shots'][0]['note'] = new_note
        drive.files = {
            'remote-root': {'id': 'remote-root', 'name': '冒险', 'parents': ['root'],
                            'mimeType': 'application/vnd.google-apps.folder'},
            'remote-manifest': {'id': 'remote-manifest', 'name': '冒险资料.json',
                                'parents': ['remote-root'], 'mimeType': 'application/json',
                                'blob': json.dumps(remote).encode()},
            'remote-template': {'id': 'remote-template', 'name': 'template.png',
                                'mimeType': 'image/png', 'blob': TEMPLATE},
            'remote-photo': {'id': 'remote-photo', 'name': 'actual.png',
                             'mimeType': 'image/png', 'blob': PHOTO_ONE},
        }
        held = []
        self.context.route('https://www.googleapis.com/drive/v3/files/remote-manifest?alt=media',
                           lambda route: held.append(route))
        self.page.locator('[data-tab="settings"]').click()
        self.page.locator('#clientId').fill('test-client.apps.googleusercontent.com')
        self.page.locator('#saveClient').click()
        self.page.locator('[data-tab="adventure"]').click()
        self.view('cloud')
        self.page.locator('[data-adv18="connect"]').click()
        for _ in range(200):
            if held:
                break
            self.page.wait_for_timeout(10)
        self.assertEqual(len(held), 1, 'Expected remote manifest download to be pending')

        # View a previously saved field while reconnect is still loading. It is
        # not a draft and must not mask the newer remote value after the merge.
        self.view('compare')
        note = self.page.locator('#adv18-shot-note')
        expect(note).to_have_value(old_note)
        self.assertEqual(note.evaluate('(el) => el.value === el.defaultValue'), True)
        held[0].fulfill(content_type='application/json',
                        headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(remote))
        self.wait_synced()
        self.assertEqual(self.data()['shots'][0]['note'], new_note)
        expect(note).to_have_value(new_note)
        self.assertEqual(note.evaluate('(el) => el.defaultValue'), new_note)
        self.assertEqual(drive.unhandled, [])
