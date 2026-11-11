"""Validate the actual inline JavaScript, worker and PWA manifest."""
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            attributes = dict(attrs)
            self.active = 'src' not in attributes and attributes.get('type', '') in ('', 'text/javascript', 'module')
            if self.active:
                self.sources.append('')

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.sources[-1] += data


def check(root=ROOT):
    parser = Scripts()
    parser.feed((root / 'index.html').read_text())
    if not parser.sources:
        raise ValueError('No inline JavaScript found; refusing empty syntax check')
    with tempfile.TemporaryDirectory() as temporary:
        for i, source in enumerate(parser.sources):
            path = Path(temporary) / f'inline-{i}.js'
            path.write_text(source)
            subprocess.run(['node', '--check', str(path)], check=True)
    subprocess.run(['node', '--check', str(root / 'sw.js')], check=True)
    manifest = json.loads((root / 'manifest.webmanifest').read_text())
    if manifest.get('start_url') != './' or manifest.get('scope') != './':
        raise ValueError('Manifest must work under the repository Pages subpath')
    print(f'PASS: {len(parser.sources)} inline script(s), sw.js and PWA manifest')


if __name__ == '__main__':
    check()
