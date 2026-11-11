"""Basketball regression tests with synthetic records and mocked Google transport.

CSV/XLSX parsing, calculations, IndexedDB and playback run in the real browser.
No real Google account or private training workbook is used by these tests.
"""
import base64
import csv
import io
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse
import zipfile
from xml.sax.saxutils import escape

from playwright.sync_api import expect

from browser_support import BrowserTestCase, ROOT


ACTIONS = ['原地投篮', '一次突破上篮', '篮下反篮', '篮下直接终结', '一次突破急停跳投']
ROOT_ID = 'fixture_root_123456789'
MIME_FOLDER = 'application/vnd.google-apps.folder'
# Synthetic 16x16 blue H.264 clip; generated with ffmpeg, contains no user data.
VIDEO = base64.b64decode('AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAMwbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAA+gAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAlt0cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAA+gAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAABAAAAAQAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAPoAAAAAAABAAAAAAHTbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAABAAAAAQABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABfm1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAT5zdGJsAAAAvnN0c2QAAAAAAAAAAQAAAK5hdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAABAAEABIAAAASAAAAAAAAAABFUxhdmM2MS4xOS4xMDEgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAANGF2Y0MBZAAK/+EAF2dkAAqs2V7ARAAAAwAEAAADABA8SJZYAQAGaOvjyyLA/fj4AAAAABBwYXNwAAAAAQAAAAEAAAAUYnRydAAAAAAAABa4AAAAAAAAABhzdHRzAAAAAAAAAAEAAAACAAAgAAAAABRzdHNzAAAAAAAAAAEAAAABAAAAHHN0c2MAAAAAAAAAAQAAAAEAAAACAAAAAQAAABxzdHN6AAAAAAAAAAAAAAACAAACywAAAAwAAAAUc3RjbwAAAAAAAAABAAADYAAAAGF1ZHRhAAAAWW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJhcHBsAAAAAAAAAAAAAAAALGlsc3QAAAAkqXRvbwAAABxkYXRhAAAAAQAAAABMYXZmNjEuNy4xMDMAAAAIZnJlZQAAAt9tZGF0AAACrQYF//+p3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzEwOCAzMWUxOWY5IC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMyAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9jaz0xOjA6MCBhbmFseXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVkX3JlZj0xIG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBkZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hyb21hX3FwX29mZnNldD0tMiB0aHJlYWRzPTEgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW1hdGU9MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0zIGJfcHlyYW1pZD0yIGJfYWRhcHQ9MSBiX2JpYXM9MCBkaXJlY3Q9MSB3ZWlnaHRiPTEgb3Blbl9nb3A9MCB3ZWlnaHRwPTIga2V5aW50PTI1MCBrZXlpbnRfbWluPTIgc2NlbmVjdXQ9NDAgaW50cmFfcmVmcmVzaD0wIHJjX2xvb2thaGVhZD00MCByYz1jcmYgbWJ0cmVlPTEgY3JmPTIzLjAgcWNvbXA9MC42MCBxcG1pbj0wIHFwbWF4PTY5IHFwc3RlcD00IGlwX3JhdGlvPTEuNDAgYXE9MToxLjAwAIAAAAAWZYiEABT//uzafgU3DFb59dMhveABgQAAAAhBmiFsQS/+4A==')


def records(counts, legacy=False):
    rows = []
    for action, (shots, made) in zip(ACTIONS, counts):
        label = '突破急停跳投' if legacy and action == ACTIONS[-1] else action
        for i in range(shots):
            rows.append({'clip': f'{len(rows) + 1}.mp4', 'action': label,
                         'result': '成功' if i < made else '失败', 'note': 'Synthetic fixture'})
    return rows


def folder(identifier, name, counts, legacy=False):
    rows = records(counts, legacy)
    return {'id': identifier, 'name': name, 'savedAt': 1, 'records': rows,
            'files': [{'id': f'{identifier}-{i}', 'name': row['clip'], 'kind': 'video',
                       'modifiedTime': 'fixture-v1', 'size': len(VIDEO)}
                      for i, row in enumerate(rows)]}


def xlsx_bytes(sheets):
    """Produce a genuine tiny OOXML workbook, not a fake XLSX API result."""
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml',
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                      for i in range(1, len(sheets) + 1)) + '</Types>')
        archive.writestr('_rels/.rels',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        archive.writestr('xl/workbook.xml',
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            + ''.join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                      for i, (name, _) in enumerate(sheets, 1)) + '</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                      for i in range(1, len(sheets) + 1)) + '</Relationships>')
        for i, (_, rows) in enumerate(sheets, 1):
            xml_rows = []
            for number, row in enumerate(rows, 1):
                cells = ''.join(f'<c r="{chr(65 + col)}{number}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'
                                for col, value in enumerate(row))
                xml_rows.append(f'<row r="{number}">{cells}</row>')
            archive.writestr(f'xl/worksheets/sheet{i}.xml',
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                + ''.join(xml_rows) + '</sheetData></worksheet>')
    return result.getvalue()


class BasketballTests(BrowserTestCase):
    def open_app(self):
        self.page.goto(self.base_url)
        expect(self.page.locator('#page')).not_to_be_empty()

    def seed(self, folders, cache=False):
        self.open_app()
        self.page.evaluate('''async ({folders, cache, video}) => {
            const db = await new Promise((resolve, reject) => {
                const req = indexedDB.open('hooplog-offline-v1', 2);
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => reject(req.error);
            });
            await new Promise((resolve, reject) => {
                const tx = db.transaction(['folders', 'videos'], 'readwrite');
                for (const f of folders) tx.objectStore('folders').put(f);
                if (cache) {
                    const file = folders[0].files[0];
                    tx.objectStore('videos').put({id:file.id, folderId:folders[0].id,
                        modifiedTime:file.modifiedTime, size:video.length,
                        blob:new Blob([new Uint8Array(video)], {type:'video/mp4'})});
                }
                tx.oncomplete = resolve; tx.onerror = () => reject(tx.error);
            });
            db.close();
        }''', {'folders': folders, 'cache': cache, 'video': list(VIDEO)})
        self.page.reload()
        expect(self.page.locator('[data-pick]')).to_have_count(len(folders))

    def mock_drive(self, workbook, name):
        """Mock transport and OAuth only; actual app import code remains intact."""
        self.requests = []
        self.page.route('https://accounts.google.com/gsi/client', lambda route: route.fulfill(
            content_type='application/javascript', body='''window.google={accounts:{oauth2:{
                initTokenClient:(options)=>{window.testOAuthScope=options.scope;
                    return {requestAccessToken:()=>options.callback({access_token:'synthetic-token',expires_in:3600})}},
                revoke:(_token, callback)=>callback()
            }}};'''))
        def handle(route):
            request = route.request
            parsed = urlparse(request.url)
            query = parse_qs(parsed.query)
            self.requests.append({'method': request.method, 'url': request.url,
                                  'auth': request.headers.get('authorization')})
            def reply(data):
                route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
            if parsed.path == '/drive/v3/files/' + ROOT_ID:
                reply({'id': ROOT_ID, 'name': '篮球', 'mimeType': MIME_FOLDER})
            elif parsed.path == '/drive/v3/files/sheet-fixture':
                route.fulfill(status=200, body=workbook, content_type='application/octet-stream')
            elif parsed.path == '/drive/v3/files':
                parent = re.search(r"'([^']+)' in parents", query.get('q', [''])[0])
                parent = parent.group(1) if parent else ''
                if parent == ROOT_ID:
                    reply({'files': [{'id': 'session-a', 'name': '2026-10-28A', 'mimeType': MIME_FOLDER},
                                     {'id': 'session-b', 'name': '2026-11-04B', 'mimeType': MIME_FOLDER},
                                     {'id': 'sheet-fixture', 'name': name, 'mimeType': 'application/octet-stream'}]})
                elif parent in ['session-a', 'session-b']:
                    reply({'files': [{'id': parent + '-clip', 'name': '1.mp4', 'size': '100',
                                      'modifiedTime': 'fixture-v1', 'mimeType': 'video/mp4'}]})
                else:
                    route.fulfill(status=404, body='Unexpected fixture parent')
            else:
                route.fulfill(status=404, body='Unexpected fixture API URL')
        self.page.route('https://www.googleapis.com/**', handle)
        self.open_app()
        self.page.locator('[data-tab="settings"]').click()
        self.page.locator('#clientId').fill('synthetic-test.apps.googleusercontent.com')
        self.page.locator('#saveClient').click()
        self.page.locator('#folderUrl').fill(ROOT_ID)
        self.page.locator('#syncRoot').click()
        expect(self.page.locator('#importStatus')).to_contain_text('同步成功', timeout=15000)

    def test_csv_drive_import_readonly_scope_and_quoted_notes(self):
        rows = [['文件夹', '视频文件名', '动作', '结果', '备注'],
                ['2026-10-28A', '1.mp4', '篮下反篮', '成功', 'Comma, and "quoted" note'],
                ['2026-11-04B', '1.mp4', '突破急停跳投', '失败', 'Second folder']]
        text = io.StringIO()
        csv.writer(text).writerows(rows)
        self.mock_drive(('\ufeff' + text.getvalue()).encode(), '记录.csv')
        expect(self.page.locator('#importStatus')).to_contain_text('2 个子文件夹，2 行 Excel，2 个视频匹配')
        self.assertEqual(self.page.evaluate('window.testOAuthScope'), 'https://www.googleapis.com/auth/drive.readonly')
        self.assertTrue(all(r['method'] == 'GET' and r['auth'] == 'Bearer synthetic-token' for r in self.requests))
        self.page.locator('[data-tab="folders"]').click()
        self.page.locator('[data-pick="session-a"]').click()
        self.page.locator('[data-tab="clips"]').click()
        expect(self.page.locator('.clip')).to_contain_text('Comma, and "quoted" note')
        self.page.locator('[data-filter="篮下反篮"]').click()
        expect(self.page.locator('.clip')).to_have_count(1)

    def test_real_xlsx_import_multiple_sheets_and_skips_summary_sheet(self):
        sheetjs = Path(os.environ.get('SHEETJS_PATH', ROOT / '.cache' / 'xlsx.full.min.js'))
        self.assertTrue(sheetjs.is_file(), f'Real SheetJS fixture missing: {sheetjs}; run documented dependency setup')
        # Exercise the application's existing CDN fallback with its exact version.
        # The primary 0.20.3 distribution is not claimed as verified here.
        self.page.route('https://cdn.sheetjs.com/**', lambda route: route.abort())
        self.page.route('https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js',
                        lambda route: route.fulfill(content_type='application/javascript', path=str(sheetjs)))
        data = xlsx_bytes([
            ('训练一', [['文件夹名称', '视频名称', '动作', '结果', '备注'],
                      ['2026-10-28A', '1.mp4', '篮下反篮', '成功', 'Excel fixture']]),
            ('训练二', [['2026-11-04B', '1.mp4', '一次突破急停跳投', '失败', 'No header supported']]),
            ('汇总', [['2026-11-04B', '1.mp4', '原地投篮', '成功', 'Must not double count']]),
        ])
        self.mock_drive(data, '记录.xlsx')
        self.assertEqual(self.page.evaluate('XLSX.version'), '0.18.5')
        expect(self.page.locator('#importStatus')).to_contain_text('2 行 Excel，2 个视频匹配')
        self.page.locator('[data-tab="folders"]').click()
        self.page.locator('[data-pick="session-a"]').click()
        self.page.locator('[data-tab="stats"]').click()
        self.page.locator('[data-v13-toggle]').click()
        self.page.locator('[data-stat-mode="single"]').click()
        expect(self.page.locator('.hero')).to_contain_text('出手 1 · 命中 1')
        expect(self.page.locator('.shot').nth(2)).to_contain_text('1 中 / 1 投')

    def test_statistics_single_summary_comparison_and_trend_arrows(self):
        old_counts = [(2, 1)] * 5
        new_counts = [(3, 2), (1, 0), (2, 1), (2, 2), (4, 1)]
        old = folder('old', '2026-10-28A', old_counts, legacy=True)
        old['records'] += [{'clip': '11.mp4', 'action': '失误', 'result': '', 'note': ''},
                           {'clip': '12.mp4', 'action': '无效运球', 'result': '', 'note': ''}]
        self.seed([old, folder('new', '2026-11-04B', new_counts)])
        self.page.locator('[data-tab="stats"]').click()
        expect(self.page.locator('[data-v13-toggle]')).to_have_attribute('aria-expanded', 'false')
        expect(self.page.locator('.v13-settings')).to_have_count(0)
        self.assertEqual(self.page.locator('.v13-action').evaluate_all('(els)=>els.map(e=>e.getAttribute("aria-label"))'),
                         [name + '对比' for name in ACTIONS])
        self.assertEqual(self.page.locator('.v13-score .v13-figure').all_text_contents(), ['10', '12'])
        for i, ((old_shots, old_made), (new_shots, new_made)) in enumerate(zip(old_counts, new_counts)):
            action = self.page.locator('.v13-action').nth(i)
            values = action.locator('.v13-metric').all()
            self.assertEqual(values[0].locator('.v13-figure').all_text_contents(), [str(old_shots), str(new_shots)])
            self.assertEqual(values[1].locator('.v13-figure').all_text_contents(), [str(old_made), str(new_made)])
            self.assertEqual(values[2].locator('.v13-figure').all_text_contents(),
                             [f'{100 * old_made / old_shots:.1f}%', f'{100 * new_made / new_shots:.1f}%'])
        # Fixed expected directions exercise the straight, colored arrows.
        for index, color in [(0, '#12915d'), (1, '#d23e4b'), (2, '#8996a7')]:
            arrow = self.page.locator('.v13-action').nth(index).locator('.v13-metric').first.locator('svg path').first
            expect(arrow).to_have_attribute('stroke', color)
            self.assertRegex(arrow.get_attribute('d'), r'^M [\d.]+ [\d.]+ L [\d.]+ [\d.]+$')
        self.page.locator('[data-tab="folders"]').click()
        self.page.locator('[data-pick="old"]').click()
        self.page.locator('[data-tab="stats"]').click()
        self.page.locator('[data-v13-toggle]').click()
        self.page.locator('[data-stat-mode="single"]').click()
        self.assertEqual(self.page.locator('.shot .row b:first-child').all_text_contents(), ACTIONS)
        expect(self.page.locator('.hero')).to_contain_text('出手 10 · 命中 5')
        expect(self.page.locator('.grid2')).to_contain_text('无效运球1失误1')
        self.page.locator('[data-stat-mode="summary"]').click()
        self.assertEqual(self.page.locator('.shot .row b:first-child').all_text_contents(), ACTIONS)
        expect(self.page.locator('.hero')).to_contain_text('出手 22 · 命中 11')
        expect(self.page.locator('.hero .pill')).to_have_text('50.0%')
        for i, ((old_shots, old_made), (new_shots, new_made)) in enumerate(zip(old_counts, new_counts)):
            expect(self.page.locator('.shot').nth(i)).to_contain_text(f'{old_made + new_made} 中 / {old_shots + new_shots} 投')

    def test_trend_angles_use_absolute_metric_baselines_and_saturate(self):
        counts = [(0, 0), (1, 1), (2, 1), (20, 6)]
        names = ['2026-10-14A', '2026-10-21A', '2026-10-28A', '2026-11-04A']
        self.seed([folder(str(i), name, [standing] + [(1, 1)] * 4)
                   for i, (name, standing) in enumerate(zip(names, counts))])
        self.page.locator('[data-tab="stats"]').click()
        action = self.page.locator('.v13-action').first
        # Every arrow is a single straight line; angle is based on absolute
        # change relative to the metric's daily scale, not percentage growth.
        angles = []
        for path in action.locator('.v13-metric').first.locator('.v13-arrow-svg path:first-child').all():
            points = [float(v) for v in re.findall(r'-?[\d.]+', path.get_attribute('d'))]
            x1, y1, x2, y2 = points
            angles.append(math.degrees(math.atan2(y1 - y2, x2 - x1)))
        self.assertEqual(len(angles), 3)
        self.assertAlmostEqual(angles[0], angles[1], places=8)
        self.assertAlmostEqual(angles[0], 34 * (1 - math.exp(-1 / 7)), places=8)
        self.assertAlmostEqual(angles[2], 34 * (1 - math.exp(-18 / 7)), places=8)
        self.assertLess(angles[2], 34)

    def test_same_weekday_recommendation_manual_reset_and_same_day_folders(self):
        names = ['2026-10-14A', '2026-10-21A', '2026-10-28A', '2026-11-04A',
                 '2026-11-05A', '2026-11-11A', '2026-11-11B']
        self.seed([folder(str(i), name, [(2, 1)] * 5) for i, name in enumerate(names)])
        self.page.locator('[data-tab="stats"]').click()
        self.page.locator('[data-v13-toggle]').click()
        self.assertEqual(self.page.locator('.v12-chip').evaluate_all('(els)=>els.map(e=>e.title)'),
                         ['2026-10-28A', '2026-11-04A', '2026-11-11A', '2026-11-11B'])
        expect(self.page.locator('.v13-score .v13-figure')).to_have_count(4)
        self.page.locator('[data-stat-picker-toggle]').click()
        self.page.locator('[data-stat-folder="4"]').check()
        expect(self.page.locator('.v12-picker-label')).to_have_text('自定义对比')
        expect(self.page.locator('.v13-score .v13-figure')).to_have_count(5)
        self.page.locator('[data-stat-reset]').click()
        expect(self.page.locator('[data-stat-folder="4"]')).not_to_be_checked()
        expect(self.page.locator('.v13-score .v13-figure')).to_have_count(4)
        self.page.locator('[data-stat-mode="summary"]').click()
        expect(self.page.locator('.hero')).to_contain_text('所选 4 场')
        expect(self.page.locator('.hero')).to_contain_text('出手 40 · 命中 20')

    def test_video_filters_offline_blob_playback_and_cache_bytes_survive(self):
        training = folder('cached-folder', '2026-10-28A', [(1, 1)] * 5)
        self.seed([training], cache=True)
        self.page.locator('[data-tab="clips"]').click()
        expect(self.page.locator('.clip')).to_have_count(5)
        self.page.locator('[data-filter="篮下反篮"]').click()
        expect(self.page.locator('.clip')).to_have_count(1)
        expect(self.page.locator('.clip')).to_contain_text('3.mp4')
        self.page.locator('[data-filter="未缓存"]').click()
        expect(self.page.locator('.clip')).to_have_count(4)
        remote = []
        self.page.on('request', lambda request: remote.append(request.url) if 'googleapis.com' in request.url else None)
        self.page.locator('.clip').first.click()
        expect(self.page.locator('#videoOverlay')).to_have_class('player hide')
        expect(self.page.locator('#toast')).to_contain_text('尚未缓存')
        self.context.set_offline(True)
        self.page.locator('[data-filter="已缓存"]').click()
        expect(self.page.locator('.clip')).to_have_count(1)
        self.page.locator('.clip').click()
        expect(self.page.locator('#videoOverlay')).not_to_have_class('player hide')
        self.page.wait_for_function('document.querySelector("#videoPlayer").readyState >= 2')
        self.assertTrue(self.page.locator('#videoPlayer').get_attribute('src').startswith('blob:'))
        self.page.locator('#closeVideo').click()
        self.context.set_offline(False)
        self.page.reload()
        video = self.page.evaluate('''async () => {
            const db = await new Promise(ok => {const r=indexedDB.open('hooplog-offline-v1',2);r.onsuccess=()=>ok(r.result)});
            const data = await new Promise(ok => {const r=db.transaction('videos').objectStore('videos').getAll();r.onsuccess=()=>ok(r.result)});
            const bytes = await data[0].blob.arrayBuffer();db.close();
            return {count:data.length, bytes:Array.from(new Uint8Array(bytes))};
        }''')
        self.assertEqual(video, {'count': 1, 'bytes': list(VIDEO)})
        self.assertEqual(remote, [])

    def test_training_real_timers_modes_probability_boundary_and_history(self):
        self.open_app()
        self.page.locator('[data-tab="training"]').click()
        self.page.locator('[data-train14-open]').click()
        self.assertEqual(self.page.locator('#train14-speed option').evaluate_all('(els)=>els.map(e=>e.value)'),
                         ['6000', '7000', '8000', '9000'])
        self.page.locator('#train14-speed').select_option('6000')
        self.page.locator('[data-train14-focus]').click()
        self.assertIn('training-v14-focus', self.page.locator('body').get_attribute('class'))
        self.page.locator('[data-train14-focus]').click()
        for mode, random_value, direction in [('direct', .59, 'right'), ('foot', .6, 'left'), ('help', .2, 'right')]:
            self.page.locator('#train14-mode').select_option(mode)
            self.page.locator('#train14-hide').set_checked(mode != 'direct')
            self.page.evaluate('(value)=>{Math.random=()=>value}', random_value)
            self.page.locator('[data-train14-play]').click()
            expect(self.page.locator('#train14-mode')).to_be_disabled()
            self.page.wait_for_function('Number(document.querySelector("#train14-round").textContent)>=1', timeout=10000)
            expect(self.page.locator('#train14-' + direction + '-count')).to_have_text('1')
            if mode != 'direct':
                expect(self.page.locator('#train14-big')).to_have_text('读防守！')
                if mode == 'help':
                    expect(self.page.locator('#train14-help-l')).to_have_attribute('opacity', '1')
            if mode == 'direct':
                self.page.wait_for_function('Number(document.querySelector("#train14-round").textContent)>=2', timeout=10000)
            self.page.locator('[data-train14-play]').click()
            expect(self.page.locator('#train14-status')).to_have_text('已暂停')
        history = self.page.evaluate("JSON.parse(localStorage.getItem('hooplog_training_sessions_v15'))")
        self.assertEqual([entry['mode'] for entry in history], ['direct', 'foot', 'help'])
        for entry in history:
            self.assertEqual(entry['rounds'], entry['left'] + entry['right'])
            self.assertGreaterEqual(entry['rounds'], 1)
        self.assertGreaterEqual(history[0]['rounds'], 2)
        self.assertEqual(history[1]['left'], 1)
        self.assertEqual(history[2]['right'], 1)
        expect(self.page.locator('.train14-tip')).to_contain_text('不会通过摄像头检测你是否真的完成动作')
        self.page.reload()
        self.page.locator('[data-tab="training"]').click()
        expect(self.page.locator('.train14-history-row')).to_have_count(3)
        expect(self.page.locator('.train14-plan-pill')).to_have_text('今日已完成')
