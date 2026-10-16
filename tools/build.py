"""Build a clean extension archive using the standard library."""
from pathlib import Path
import hashlib
import re
import zipfile

root = Path(__file__).resolve().parents[1]
source = root/'layz_agentkit'
manifest = (source/'blender_manifest.toml').read_text(encoding='utf-8')
version = re.search(r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$',manifest,re.MULTILINE).group(1)
destination = root/'dist'/f'layz_agentkit-{version}.zip'
destination.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
    def add_text(path, name):
        # Fixed metadata and LF text make repeated builds reproducible.
        entry = zipfile.ZipInfo(str(name).replace('\\','/'),date_time=(1980,1,1,0,0,0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry,path.read_bytes().replace(b'\r\n',b'\n'))

    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix in {'.py','.toml'}:
            add_text(path, path.relative_to(source))
    for name in ('README.md','LICENSE'):
        if (root/name).is_file():
            add_text(root/name,name)
print(destination)
checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
(destination.parent/'SHA256SUMS.txt').write_text(f'{checksum}  {destination.name}\n',encoding='utf-8')
print(destination.parent/'SHA256SUMS.txt')
