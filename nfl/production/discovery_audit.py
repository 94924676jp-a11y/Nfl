"""Find stages that can still discover their own evidence after the freeze.

THE RULE, IN THE OWNER'S WORDS

    Before freeze, discovery is allowed. After freeze, forecast execution must
    not perform independent discovery. No stage should be able to do its own
    glob(), sorted(...)[0], "latest file", newest_lawful(), branch scan, or
    working-tree lookup. Every reader must consume declared artifacts from the
    frozen evidence contract.

WHY A STATIC AUDIT AND NOT ONLY A RUNTIME ONE

The adversarial battery already shows that dropping a newer undeclared file
into the tree changes no verdict and does not move the evidence digest. That
is a real result and it is not the whole rule: it proves the CONTRACT layer
ignores intruders, not that every stage downstream consults the contract.

A stage that globs is a stage that CAN read something the contract never
named. It may happen not to today, on this slate, with these files. Auditing
the capability rather than the occurrence is the difference between "it did
not happen" and "it cannot happen", and only the second is a boundary.

WHAT A HIT MEANS, AND WHAT IT DOES NOT

A hit is a discovery primitive in a file on the production path. It is NOT
automatically a defect:

* `newest_lawful` selecting the newest capture at or before a declared cut is
  discovery, but it is CLOCK-BOUNDED discovery and a caller that then pins the
  result is behaving correctly.
* A glob in a module-level constant, a CLI entry point, or a fixture builder
  runs before freeze and is exactly where discovery belongs.

So this reports candidates with their line and context, classifies what it
can, and leaves the judgement legible rather than emitting a number. An
auditor that graded itself would be the same defect one level up.

LIMITS
  This is a source-text (or record-level) heuristic, not a behavioural
  measurement. Every row it emits is a question for a human, the counts are a
  floor rather than a survey, and it does not know what is deliberate.
"""
from __future__ import annotations

import pathlib
import re

SPEC_VERSION = 'discovery-audit/1.0.0'

_REPO = pathlib.Path(__file__).resolve().parents[2]

#: Primitives that can reach evidence the contract did not name.
PRIMITIVES = {
    'glob': re.compile(r'\b(?:glob\.glob|\.glob\()'),
    'rglob': re.compile(r'\.rglob\('),
    'listdir': re.compile(r'\bos\.listdir\b'),
    'walk': re.compile(r'\bos\.walk\b'),
    'sorted_index': re.compile(r'sorted\([^)]*\)\s*\[\s*-?\d+\s*\]'),
    'max_by_mtime': re.compile(r'getmtime|st_mtime'),
    'newest_lawful': re.compile(r'\bnewest_lawful\b'),
    'iterdir': re.compile(r'\.iterdir\('),
}

#: Where discovery is LEGITIMATE because it runs before or outside a forecast.
PRE_FREEZE = (
    'nfl/truth/run_input.py',      # builds the contract; discovery is its job
    'nfl/tools/',                  # operator entry points
    'nfl/tests/',                  # fixtures and audits
    'nfl/research/',               # research, not the production path
)

#: Files that ARE the production forecast path.
PRODUCTION_ROOTS = ('nfl/production/',)


def _is_pre_freeze(rel: str) -> bool:
    return any(rel.startswith(p) for p in PRE_FREEZE)


def _context(lines, i):
    return '\n'.join(lines[max(0, i - 1):i + 2]).strip()[:220]


def scan(roots=PRODUCTION_ROOTS) -> dict:
    """Every discovery primitive on the production path, with context."""
    hits = []
    scanned = 0
    for root in roots:
        base = _REPO / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob('*.py')):
            rel = str(path.relative_to(_REPO))
            # The auditor's own PRIMITIVES table is full of these strings by
            # construction. Counting itself would inflate every number it
            # reports and is the cheapest possible way to look thorough.
            if '__pycache__' in rel or rel.endswith('discovery_audit.py'):
                continue
            scanned += 1
            try:
                text = path.read_text(errors='replace')
            except OSError:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                for name, rx in PRIMITIVES.items():
                    if rx.search(line):
                        hits.append({
                            'file': rel,
                            'line': i + 1,
                            'primitive': name,
                            'code': stripped[:160],
                            'context': _context(lines, i),
                            'pre_freeze_area': _is_pre_freeze(rel),
                        })
    by_file = {}
    for h in hits:
        by_file.setdefault(h['file'], []).append(h)
    by_primitive = {}
    for h in hits:
        by_primitive[h['primitive']] = by_primitive.get(h['primitive'], 0) + 1
    return {
        'spec_version': SPEC_VERSION,
        'n_files_scanned': scanned,
        'n_hits': len(hits),
        'n_files_with_hits': len(by_file),
        'by_primitive': dict(sorted(by_primitive.items(),
                                    key=lambda kv: -kv[1])),
        'files': {f: len(v) for f, v in sorted(by_file.items(),
                                               key=lambda kv: -len(kv[1]))},
        'hits': hits,
        'reading': (
            'A hit is a CAPABILITY, not an occurrence. Auditing what a stage '
            'CAN read rather than what it did read is the difference between '
            '"it did not happen" and "it cannot happen", and only the second '
            'is a boundary. Each hit still needs a human judgement, which is '
            'why they are listed with context rather than scored.'),
    }


def render(report: dict, limit=25) -> str:
    out = [f"discovery audit  {report['n_hits']} hit(s) across "
           f"{report['n_files_with_hits']} of {report['n_files_scanned']} "
           f"production files",
           '',
           'by primitive: ' + ', '.join(f'{k}={v}' for k, v
                                        in report['by_primitive'].items()),
           '']
    for f, n in list(report['files'].items())[:limit]:
        out.append(f'  {n:3}  {f}')
    if len(report['files']) > limit:
        out.append(f'  ... {len(report["files"]) - limit} more')
    out += ['', report['reading']]
    return '\n'.join(out)
