"""Check the build archive without importing Blender or requiring pip packages."""
import ast
import hashlib
from pathlib import Path
import re
import zipfile

root = Path(__file__).resolve().parents[1]
source = root/'layz_agentkit'
manifest = (source/'blender_manifest.toml').read_text(encoding='utf-8')
version = re.search(r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$',manifest,re.MULTILINE).group(1)
archive = root/'dist'/f'layz_agentkit-{version}.zip'
expected = {str(p.relative_to(source)).replace('\\','/'):p for p in source.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.toml'}}
expected.update({name:root/name for name in ('README.md','LICENSE')})
tree = ast.parse((source/'__init__.py').read_text(encoding='utf-8'))
info = next(ast.literal_eval(node.value) for node in tree.body
            if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='bl_info' for target in node.targets))
assert info['version'] == tuple(map(int,version.split('.'))),'Manifest and module versions differ'
assert 'SPDX:GPL-3.0-or-later' in manifest,'Unexpected manifest license'
with zipfile.ZipFile(archive) as package:
    assert package.testzip() is None,'ZIP CRC check failed'
    assert set(package.namelist()) == set(expected),'Unexpected or missing ZIP files'
    for name,path in expected.items():
        content = package.read(name)
        assert content == path.read_bytes().replace(b'\r\n',b'\n'),f'Package differs from source: {name}'
        assert not name.startswith('/') and '..' not in Path(name).parts,'Unsafe archive path'
        if name.endswith('.py'):
            compile(content,name,'exec')
            assert b'SPDX-License-Identifier: GPL-3.0-or-later' in content,f'Missing source license: {name}'
        if name not in {'LICENSE','README.md'}:
            for private in (b'C:/Users/',b'C:\\Users\\',b'S:/Blender Projects/',b'S:\\Blender Projects\\'):
                assert private not in content,f'Local machine path in {name}'
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
assert (root/'dist'/'SHA256SUMS.txt').read_text(encoding='utf-8') == f'{checksum}  {archive.name}\n','Checksum mismatch'
print(f'PASS: {len(expected)} expected files, source parity, syntax, license, paths, ZIP CRC and SHA-256')
print(f'{checksum}  {archive.name}')
