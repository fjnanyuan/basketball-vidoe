"""Real browser + disposable storage, served under the GitHub Pages subpath."""
import functools
import os
from pathlib import Path
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class BrowserTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        handler = functools.partial(QuietHandler, directory=str(ROOT.parent))
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        cls.addClassCleanup(cls.server.server_close)
        thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(cls.server.shutdown)
        cls.base_url = f'http://127.0.0.1:{cls.server.server_port}/{ROOT.name}/'
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        name = os.environ.get('HOOPLOG_BROWSER', 'chromium')
        if name not in ('chromium', 'webkit'):
            raise ValueError('HOOPLOG_BROWSER must be chromium or webkit')
        options = {'headless': True}
        executable = os.environ.get('HOOPLOG_CHROMIUM_PATH') or shutil.which('chromium')
        if name == 'chromium' and executable:
            options['executable_path'] = executable
            options['args'] = ['--no-sandbox']
        cls.browser = getattr(cls.playwright, name).launch(**options)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        super().setUp()
        self.context = self.browser.new_context(
            viewport={'width': 390, 'height': 844},
            timezone_id='Asia/Tokyo', has_touch=True,
        )
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page_errors = []
        self.page.on('pageerror', lambda error: self.page_errors.append(str(error)))

    def tearDown(self):
        self.assertEqual(self.page_errors, [], 'Uncaught browser errors')
        super().tearDown()
