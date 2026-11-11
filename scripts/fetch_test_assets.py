"""Fetch the app's existing SheetJS fallback for offline, real XLSX regression tests.

Test dependency only: it is never copied to the public Pages artifact.
"""
import base64
import hashlib
import io
from pathlib import Path
import tarfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://registry.npmjs.org/xlsx/-/xlsx-0.18.5.tgz'
# Published npm SRI for the exact fallback version already referenced by the app.
SRI = 'dmg3LCjBPHZnQp5/F/+nnTa+miPJxUXB6vtk42YjBBKayDNagxGEeIdWApkYPOf3Z3pm3k62Knjzp7lMeTEtFQ=='


def main():
    with urlopen(URL, timeout=60) as response:
        archive = response.read()
    actual = base64.b64encode(hashlib.sha512(archive).digest()).decode()
    if actual != SRI:
        raise SystemExit('SheetJS package integrity mismatch; refusing test asset')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as package:
        member = package.extractfile('package/dist/xlsx.full.min.js')
        if member is None:
            raise SystemExit('SheetJS distribution missing')
        source = member.read()
    destination = ROOT / '.cache' / 'xlsx.full.min.js'
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes(source)
    print('Verified SheetJS 0.18.5 (existing fallback), saved to .cache/xlsx.full.min.js')


if __name__ == '__main__':
    main()
