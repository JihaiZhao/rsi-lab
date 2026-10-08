"""Export a credential-free runtime once from the pinned local role image."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'work/runtime/codex-0.154.0'


def prepare():
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / 'runtime.tar.gz'
    manifest = CACHE / 'manifest.json'
    if archive.exists() or manifest.exists():
        raise RuntimeError('Runtime cache already exists; refusing to replace it')
    image = subprocess.check_output(['docker', 'image', 'inspect', 'rsi-terra-roles:0.154.0',
                                    '--format', '{{.Id}}'], text=True).strip()
    versions = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none',
        '--entrypoint', 'sh', image, '-c', 'node --version && codex --version'], text=True).splitlines()
    if versions != ['v22.23.3', 'codex-cli 0.154.0']:
        raise RuntimeError('Unexpected runtime versions: ' + repr(versions))
    with archive.open('xb') as f:
        subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'tar', image,
            '-czf', '-', '-C', '/', 'usr/local/bin/node', 'usr/local/lib/node_modules',
            'etc/ssl/certs/ca-certificates.crt'], stdout=f, check=True)
    manifest.write_text(json.dumps({'image_id':image, 'node':'22.23.3', 'codex':'0.154.0',
        'platform':'linux-x86_64', 'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2)+'\n')
    print('Cached runtime:', archive)

if __name__ == '__main__':prepare()
