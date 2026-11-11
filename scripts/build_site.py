"""Build an allowlisted, identifiable static Pages artifact without user data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = ('index.html', 'sw.js', 'manifest.webmanifest')


def build(output, commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('A complete 40-character Git commit SHA is required')
    output = Path(output)
    if output.is_symlink():
        raise ValueError('Output directory must not be a symbolic link')
    output = output.resolve()
    if output == ROOT or output in ROOT.parents or ROOT / '.git' == output or ROOT / '.git' in output.parents:
        raise ValueError('Output must not overwrite the checkout or Git metadata')
    output.mkdir(parents=True, exist_ok=True)
    allowed = {*PUBLIC_FILES, 'version.json', '.nojekyll'}
    if any(p.name not in allowed or p.is_symlink() or not p.is_file() for p in output.iterdir()):
        raise ValueError('Output contains unexpected files; choose an empty build directory')
    html = (ROOT / 'index.html').read_text()
    html = html.replace('</head>', f'<meta name="hooplog-build" content="{commit}">\n</head>', 1)
    if f'name="hooplog-build" content="{commit}"' not in html:
        raise ValueError('Could not insert build identity')
    (output / 'index.html').write_text(html)
    worker, count = re.subn(r"const CACHE='hooplog-shell-[^']+';", f"const CACHE='hooplog-shell-v18-{commit}';", (ROOT / 'sw.js').read_text(), count=1)
    if count != 1:
        raise ValueError('Worker shell cache marker not found')
    (output / 'sw.js').write_text(worker)
    (output / 'manifest.webmanifest').write_bytes((ROOT / 'manifest.webmanifest').read_bytes())
    version = {'version': 'v18', 'commit': commit, 'sha256': {
        name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in PUBLIC_FILES
    }}
    (output / 'version.json').write_text(json.dumps(version, indent=2) + '\n')
    (output / '.nojekyll').touch()
    print(f'Built {output}: v18 commit {commit}; public files only')
    return version


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', default='_site')
    cli.add_argument('--commit', default=None)
    args = cli.parse_args()
    sha = args.commit or subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    build(args.output, sha)
