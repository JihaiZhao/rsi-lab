"""Portable extension bundle: one source format, compiled per native runtime."""
import ast
import difflib
import json
import re
import shlex
from pathlib import Path

from native_bundle import bundle_hash  # Same hashing as archived experiments.

RUNTIME_ROOT = '/opt/rsi-harness'
SUFFIXES = {'.md', '.py', '.js', '.json'}
MAX_BYTES = 2 * 1024 * 1024
HOOK_EVENTS = ('session_start', 'pre_tool', 'post_tool', 'stop')
COMPONENTS = ('instructions', 'skill', 'tool', 'mcp', 'hook', 'memory')
INTERPRETERS = ('python3', 'node')


def component_of(path):
    """Map a bundle-relative path to its component; None for support files."""
    head = path.split('/')[0]
    return {'instructions.md': 'instructions', 'skills': 'skill', 'tools': 'tool',
            'mcp': 'mcp', 'hooks.json': 'hook', 'memory': 'memory'}.get(head)


def files(folder):
    folder = Path(folder)
    return sorted(str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file())


def components(folder):
    """Components present in a bundle, ignoring an empty instructions entry."""
    folder = Path(folder)
    found = {component_of(f) for f in files(folder)} - {None}
    if 'instructions' in found and not (folder/'instructions.md').read_text().strip():
        found.discard('instructions')
    return sorted(found)


def complexity(folder):
    """Non-blank lines across all bundle files; the regularizer used at selection."""
    return sum(1 for f in files(folder) for line in (Path(folder)/f).read_text().splitlines() if line.strip())


def _command_errors(where, command, args):
    errors = []
    if command not in INTERPRETERS:
        errors.append(f'{where}: command must be one of {INTERPRETERS}')
    if not args or not all(isinstance(a, str) for a in args):
        errors.append(f'{where}: args must be a non-empty list of strings')
    elif not args[0].startswith(RUNTIME_ROOT + '/') or '..' in args[0]:
        errors.append(f'{where}: script must live under {RUNTIME_ROOT}')
    return errors


def read_hooks(folder):
    path = Path(folder)/'hooks.json'
    return json.loads(path.read_text()) if path.exists() else {}


def read_mcp(folder):
    path = Path(folder)/'mcp/servers.json'
    return json.loads(path.read_text()) if path.exists() else {}


def read_smoke(folder):
    path = Path(folder)/'smoke.json'
    return json.loads(path.read_text()) if path.exists() else []


def validate(folder, capabilities):
    """Static checks only. Executable behaviour is checked by the gate's smoke tests."""
    folder = Path(folder)
    errors = []
    if not (folder/'instructions.md').is_file():
        errors.append('Missing instructions.md')
    size = 0
    for p in folder.rglob('*'):
        if p.is_symlink():
            errors.append('Symlink: '+str(p.relative_to(folder))); continue
        if not p.is_file():
            continue
        rel = str(p.relative_to(folder))
        size += p.stat().st_size
        if p.suffix not in SUFFIXES:
            errors.append('Unsupported file type: '+rel); continue
        if rel == 'settings.json':
            errors.append('settings.json is runtime-specific; declare hooks in hooks.json'); continue
        component = component_of(rel)
        if rel != 'smoke.json' and component is None:
            errors.append('File outside a known component: '+rel)
        elif component and component not in capabilities.components:
            errors.append(f'{rel}: component {component!r} is not supported by {capabilities.name}')
        try:
            text = p.read_text()
            if p.suffix == '.py':
                ast.parse(text)
            if p.suffix == '.json':
                json.loads(text)
        except (UnicodeError, SyntaxError, ValueError) as error:
            errors.append(f'{rel}: {error}')
    if size > MAX_BYTES:
        errors.append('Bundle exceeds 2 MiB')
    if errors:
        return errors
    hooks = read_hooks(folder)
    if not isinstance(hooks, dict) or set(hooks) - set(HOOK_EVENTS):
        errors.append(f'hooks.json keys must be a subset of {HOOK_EVENTS}')
    else:
        for event, entries in hooks.items():
            for i, entry in enumerate(entries if isinstance(entries, list) else [None]):
                where = f'hooks.json {event}[{i}]'
                if not isinstance(entry, dict) or set(entry) - {'command', 'args', 'matcher', 'timeout'}:
                    errors.append(where+': expected {command, args, matcher?, timeout?}'); continue
                errors += _command_errors(where, entry.get('command'), entry.get('args'))
                if not isinstance(entry.get('timeout', 30), int) or not 1 <= entry.get('timeout', 30) <= 60:
                    errors.append(where+': timeout must be 1-60 seconds')
    servers = read_mcp(folder)
    if not isinstance(servers, dict):
        errors.append('mcp/servers.json must map server names to {command, args}')
    else:
        for name, server in servers.items():
            where = 'mcp server '+name
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', name):
                errors.append(where+': invalid name')
            if not isinstance(server, dict) or set(server) - {'command', 'args'}:
                errors.append(where+': expected {command, args}'); continue
            errors += _command_errors(where, server.get('command'), server.get('args'))
    executable = {c for c in components(folder) if c in ('tool', 'mcp', 'hook')}
    smoke = read_smoke(folder)
    if not isinstance(smoke, list) or not all(isinstance(s, dict) and isinstance(s.get('name'), str) for s in smoke):
        errors.append('smoke.json must be a list of {name, command, args, stdin?, expect_exit?, timeout?}')
    elif executable and not smoke:
        errors.append('Executable components require smoke.json tests: '+', '.join(sorted(executable)))
    else:
        for i, test in enumerate(smoke):
            errors += _command_errors(f'smoke.json[{i}]', test.get('command'), test.get('args'))
    return errors


def entry_prompt(folder, runtime_note):
    return (Path(folder)/'instructions.md').read_text() + (
        f'\nYour reusable harness files are in {RUNTIME_ROOT}. '
        'Use only the supplied task data and in-episode measurements. Do not seek benchmark solutions. '
        f'{runtime_note} The task instruction and its experiment/time budgets take precedence over harness advice.')


def claude_settings(folder):
    """Compile neutral hooks to Claude Code settings.json hooks."""
    events = {'session_start': 'SessionStart', 'pre_tool': 'PreToolUse',
              'post_tool': 'PostToolUse', 'stop': 'Stop'}
    hooks = {}
    for event, entries in read_hooks(folder).items():
        for entry in entries:
            command = ' '.join([entry['command'], *map(shlex.quote, entry['args'])])
            group = {'hooks': [{'type': 'command', 'command': command, 'timeout': entry.get('timeout', 30)}]}
            if event in ('pre_tool', 'post_tool'):
                group['matcher'] = entry.get('matcher', '*')
            hooks.setdefault(events[event], []).append(group)
    return {'hooks': hooks} if hooks else None


def mcp_servers(folder):
    return [{'name': name, 'transport': 'stdio', 'command': s['command'], 'args': s['args']}
            for name, s in sorted(read_mcp(folder).items())]


def changed_files(parent, candidate):
    paths = set(files(parent)) | set(files(candidate))
    read = lambda root, p: (Path(root)/p).read_bytes() if (Path(root)/p).is_file() else None
    return sorted(p for p in paths if read(parent, p) != read(candidate, p))


def diff(parent, candidate):
    parent, candidate = Path(parent), Path(candidate)
    parts = []
    for rel in sorted(set(files(parent)) | set(files(candidate))):
        before = (parent/rel).read_text().splitlines(True) if (parent/rel).exists() else []
        after = (candidate/rel).read_text().splitlines(True) if (candidate/rel).exists() else []
        parts.extend(difflib.unified_diff(before, after, fromfile='parent/'+rel, tofile='candidate/'+rel))
    return ''.join(parts)


__all__ = ['bundle_hash', 'validate', 'components', 'complexity', 'files', 'component_of',
           'claude_settings', 'mcp_servers', 'changed_files', 'diff', 'entry_prompt', 'read_smoke', 'read_hooks', 'read_mcp']
