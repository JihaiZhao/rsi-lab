"""Offline runtime installation; no network fallback or account data."""
import hashlib
import json
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / 'work/runtime/codex-0.154.0'
INSTALL_COMMAND = '''set -eu
[ "$(uname -m)" = x86_64 ]
mkdir -p /opt/rsi-runtime /usr/local/bin
tar -xzf /tmp/rsi-codex-runtime.tar.gz -C /opt/rsi-runtime
base=/opt/rsi-runtime/usr/local
ln -sf "$base/bin/node" /usr/local/bin/node
ln -sf "$base/lib/node_modules/@openai/codex/bin/codex.js" /usr/local/bin/codex
ln -sf "$base/lib/node_modules/npm/bin/npm-cli.js" /usr/local/bin/npm
ln -sf "$base/lib/node_modules/npm/bin/npx-cli.js" /usr/local/bin/npx
ln -sf "$base/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/codex-path/rg" /usr/local/bin/rg
if [ ! -s /etc/ssl/certs/ca-certificates.crt ]; then
 mkdir -p /etc/ssl/certs
 cp /opt/rsi-runtime/etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
fi
[ "$(node --version)" = v22.23.3 ]
[ "$(codex --version)" = 'codex-cli 0.154.0' ]
npm --version
rg --version
rm /tmp/rsi-codex-runtime.tar.gz
'''


def validate_cache():
    archive=CACHE/'runtime.tar.gz'
    manifest=json.loads((CACHE/'manifest.json').read_text())
    if manifest.get('codex')!='0.154.0' or manifest.get('node')!='22.23.3':
        raise RuntimeError('Wrong cached runtime version')
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['sha256']:
        raise RuntimeError('Cached runtime hash mismatch')
    return archive,manifest


async def install_cached_runtime(environment, logs_dir):
    archive,manifest=validate_cache()
    await environment.upload_file(archive, '/tmp/rsi-codex-runtime.tar.gz')
    result=await environment.exec(command=INSTALL_COMMAND,user='root')
    if result.return_code:
        raise RuntimeError('Offline runtime installation failed: '+str(result.stderr))
    (Path(logs_dir)/'runtime.json').write_text(json.dumps(manifest,indent=2)+'\n')
