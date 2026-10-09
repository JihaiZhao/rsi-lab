"""Runtime adapters. The controller only talks to these interfaces."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    name: str
    components: tuple  # Portable bundle components the native harness can load.
    trajectory: str = 'atif'  # Harbor ATIF trajectory.json for task trials.
    notes: str = ''


def get(name):
    if name == 'claude_code':
        from rsi.runtimes import claude_code
        return claude_code
    if name == 'codex':
        from rsi.runtimes import codex
        return codex
    raise ValueError('Unknown runtime adapter: '+str(name))
