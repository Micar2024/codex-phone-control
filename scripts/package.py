#!/usr/bin/env python3
"""Create the checked, sanitized source archive and outer checksum."""
from pathlib import Path
import hashlib
import os
import zipfile

root = Path(__file__).resolve().parents[1]
files = []
for path in sorted(root.rglob('*')):
    rel = path.relative_to(root)
    if not path.is_file():
        continue
    if any(part in {'dist', '__pycache__', '.git', '.tools'} for part in rel.parts):
        continue
    if path.name in {'.DS_Store', 'SHA256SUMS.txt'}:
        continue
    files.append(path)

manifest = ''.join(
    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n"
    for path in files
)
(root / 'SHA256SUMS.txt').write_text(manifest, encoding='utf-8')

archive = root / 'dist' / 'codex-phone-control-hardened-20261021.zip'
prefix = 'codex-phone-control-hardened-20261021/'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for path in files + [root / 'SHA256SUMS.txt']:
        info = zipfile.ZipInfo(prefix + path.relative_to(root).as_posix())
        info.compress_type = zipfile.ZIP_DEFLATED
        mode = 0o100755 if os.access(path, os.X_OK) else 0o100644
        info.external_attr = mode << 16
        z.writestr(info, path.read_bytes())

outer = hashlib.sha256(archive.read_bytes()).hexdigest()
(root / 'dist' / 'SHA256SUMS.txt').write_text(
    f'{outer}  {archive.name}\n', encoding='utf-8')
print(f'files={len(files)} archive_bytes={archive.stat().st_size}')
print(f'archive_sha256={outer}')
