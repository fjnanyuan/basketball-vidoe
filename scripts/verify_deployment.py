"""Verify the exact published artifact, bypassing HTTP caches without deleting data."""
import argparse
import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


def verify(url, commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Expected a complete Git commit SHA')
    parts = urlsplit(url)
    if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost')):
        raise ValueError('Use HTTPS for a deployed site')
    url = url.rstrip('/') + '/'

    def read(name):
        request = Request(urljoin(url, name) + '?hooplog_verify=' + commit,
                          headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
        with urlopen(request, timeout=30) as response:
            return response.read()

    version = json.loads(read('version.json'))
    if version.get('commit') != commit or version.get('version') != 'v18':
        raise ValueError(f'Published revision differs from expected {commit}')
    for name in ('index.html', 'sw.js', 'manifest.webmanifest'):
        content = read(name)
        if hashlib.sha256(content).hexdigest() != version.get('sha256', {}).get(name):
            raise ValueError(f'{name} differs from the published artifact manifest')
        if name == 'index.html' and f'name="hooplog-build" content="{commit}"'.encode() not in content:
            raise ValueError('HTML build marker missing')
        if name == 'sw.js' and f'hooplog-shell-v18-{commit}'.encode() not in content:
            raise ValueError('Worker cache belongs to another revision')
    print(f'PASS: HTTP publication identity, HTML, worker and manifest match {commit}')
    return version


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--url', required=True)
    cli.add_argument('--commit', required=True)
    args = cli.parse_args()
    verify(args.url, args.commit)
