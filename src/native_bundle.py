"""Data-only harness boundary; candidate Python runs in the task container."""
import ast
import hashlib
import json
import re
from pathlib import Path

def bundle_hash(folder):
    h=hashlib.sha256()
    for p in sorted(Path(folder).rglob('*')):
        if p.is_symlink():raise ValueError('Symlinks cannot be hashed as a harness bundle')
        if p.is_file():h.update(str(p.relative_to(folder)).encode()+b'\0'+p.read_bytes()+b'\0')
    return h.hexdigest()

def validate_bundle(folder):
    folder=Path(folder);errors=[]
    if not (folder/'instructions.md').is_file():errors.append('Missing instructions.md')
    size=0
    for p in folder.rglob('*'):
        if p.is_symlink():errors.append('Symlink: '+str(p));continue
        if not p.is_file():continue
        size+=p.stat().st_size
        if p.suffix not in {'.md','.py','.js','.json'}:errors.append('Unsupported file: '+p.name);continue
        try:
            text=p.read_text()
            if p.suffix=='.py':ast.parse(text)
            if p.suffix=='.json':json.loads(text)
            if re.search(r'\b[A-Z][a-z]?-0\.\d+(?:-[A-Z][a-z]?-0\.\d+)+',text):
                errors.append('Literal composition: '+p.name)
        except (UnicodeError,SyntaxError,ValueError) as e:errors.append(p.name+': '+str(e))
    if size>2*1024*1024:errors.append('Bundle exceeds 2 MiB')
    settings=folder/'settings.json'
    if settings.exists():
        try:
            value=json.loads(settings.read_text())
            if not isinstance(value,dict) or set(value)-{'hooks'}:errors.append('Only native hooks may be configured')
        except ValueError:pass
    return errors
