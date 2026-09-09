"""Build the derived research artifacts into production's read-only cache.

    python3.12 nfl/tools/build_derived.py [--dest DIR]

Production builds them on demand too, but this exists so an operator can do it
deliberately -- and so a deployment can pre-warm the cache rather than paying
the regeneration cost inside the first forecast.
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from nfl.production import derived as D                         # noqa: E402

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dest', default=None)
    a = ap.parse_args()
    o = D.build(a.dest)
    print(f'{o.state.value}[{o.code}] {o.detail[:200]}')
    for k, v in o.evidence.items():
        if k != 'value':
            print(f'  {k}: {v}')
    sys.exit(0 if o.state.name == 'PASS' else 1)
