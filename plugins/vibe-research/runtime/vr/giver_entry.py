"""Convenience giver CLI; uses the same implementation as vr giver."""
import sys
from pathlib import Path
from .cli import main as vr_main

def main():
    args=sys.argv[1:]
    if '--workspace' in args:
        i=args.index('--workspace');workspace=args[i+1];args=args[:i]+args[i+2:]
    else:
        cwd=Path.cwd();workspace=str(cwd/'outputs' if (cwd/'outputs/projects.json').exists() else cwd if (cwd/'projects.json').exists() else cwd/'vibe-research-workspace')
    vr_main(['giver','--workspace',workspace,*args])
