"""Create an isolated, dependency-free Unity import test project under artifacts."""
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
project = root/'artifacts'/'unity-validation'
(project/'Assets'/'Editor').mkdir(parents=True, exist_ok=True)
(project/'Packages').mkdir(exist_ok=True)
(project/'ProjectSettings').mkdir(exist_ok=True)
(project/'Packages'/'manifest.json').write_text('{"dependencies":{}}',encoding='utf-8')
(project/'ProjectSettings'/'ProjectVersion.txt').write_text('m_EditorVersion: 6000.3.23f1\n',encoding='utf-8')
shutil.copy2(root/'tests'/'unity'/'ValidateExport.cs',project/'Assets'/'Editor'/'ValidateExport.cs')
fixtures = []
for name in ('RenamedCube','CentimetreCube','MultiObject'):
    packages = sorted((root/'artifacts'/'integration'/'exports').glob(name+'_v*'), reverse=True)
    package = next((p for p in packages if (p/'report.json').exists() and json.loads((p/'report.json').read_text(encoding='utf-8')).get('status') == 'verified'),None)
    if package is None:
        continue
    report = json.loads((package/'report.json').read_text(encoding='utf-8'))
    destination = project/'Assets'/'Fixtures'/name
    shutil.copytree(package,destination,dirs_exist_ok=True)
    fixtures.append({'assetPath':(destination/(name+'.fbx')).relative_to(project).as_posix(),
                     'triangles':report['total_triangles'],
                     'dimensions':dict(zip(('x','y','z'),report['dimensions_m']))})
(project/'fixtures.json').write_text(json.dumps({'fixtures':fixtures},indent=2),encoding='utf-8')
assert len(fixtures) >= 2,'Run Blender integration tests first'
print(project)
