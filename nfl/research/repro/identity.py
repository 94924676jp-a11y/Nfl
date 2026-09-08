"""The frozen-experiment identity gate. Stage 1 of the 2026-09-08 directive.

A prospective run may claim the label

    ABC_MPR PROSPECTIVE CONFIRMATION

only if every component of the frozen experiment's identity matches. Anything
else -- a changed leaf input, a changed module, a different row ordering, a
different dtype, a different seed, a different upstream artifact -- makes it a
different experiment, and it is labelled

    DIFFERENT_INPUT_GENERATION

That is not a failure state. It is an honest one. The failure state is a run
that quietly keeps the frozen label while standing on different bytes.

Fail-closed throughout: a missing artifact, an unreadable spec, an undeclared
field and an unhashable input are all refusals, never passes. Absence is never
success -- the recurring defect this project keeps paying for.

Rule 006 applies: the comparison values are LOADED from
`ABC_MPR_IDENTITY.json` and the spec's own hash is reported, never transcribed.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Mapping

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.join(HERE, 'ABC_MPR_IDENTITY.json')

CONFIRMED = 'ABC_MPR PROSPECTIVE CONFIRMATION'
DIFFERENT = 'DIFFERENT_INPUT_GENERATION'
REFUSED = 'IDENTITY_REFUSED'

# Every group a descriptor must declare. An undeclared group is a refusal, not
# a match: "it didn't say" and "it agreed" must never collapse into each other.
REQUIRED_GROUPS = ('derived_artifacts', 'leaf_inputs', 'source_code',
                   'panel_identity', 'dtype_contract', 'seed_protocol',
                   'draw_protocol', 'solver', 'feature_set',
                   'consumed_seasons')

FORBIDDEN_SEASONS = (2026,)


class IdentityError(RuntimeError):
    """Raised when the gate itself cannot be operated safely."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_spec(path: str = SPEC_PATH):
    """Load the frozen spec and its own hash. Never accepts a typed value."""
    if not os.path.exists(path):
        raise IdentityError(f'SPEC_ABSENT: {path}')
    raw = open(path, 'rb').read()
    if not raw:
        raise IdentityError(f'SPEC_EMPTY: {path}')
    try:
        spec = json.loads(raw)
    except ValueError as exc:
        raise IdentityError(f'SPEC_UNPARSEABLE: {path}: {exc}')
    for g in ('derived_artifacts', 'leaf_inputs', 'source_code',
              'panel_identity', 'dtype_contract', 'seed_protocol',
              'draw_protocol', 'solver', 'feature_set'):
        if g not in spec:
            raise IdentityError(f'SPEC_INCOMPLETE: missing {g}')
    return spec, hashlib.sha256(raw).hexdigest()


def _cmp_map(name, want: Mapping, got: Any, key=None):
    """Compare one declared group. Returns a list of mismatch records."""
    out = []
    if not isinstance(got, Mapping):
        return [{'group': name, 'field': '*', 'expected': 'a mapping',
                 'actual': type(got).__name__}]
    for k, wv in want.items():
        if key is not None:
            wv = wv[key] if isinstance(wv, Mapping) and key in wv else wv
        if k not in got:
            out.append({'group': name, 'field': k, 'expected': wv,
                        'actual': None, 'why': 'not declared by the run'})
            continue
        gv = got[k]
        if isinstance(wv, Mapping) and isinstance(gv, Mapping):
            for kk, wvv in wv.items():
                if kk not in gv:
                    out.append({'group': name, 'field': f'{k}.{kk}',
                                'expected': wvv, 'actual': None,
                                'why': 'not declared by the run'})
                elif gv[kk] != wvv:
                    out.append({'group': name, 'field': f'{k}.{kk}',
                                'expected': wvv, 'actual': gv[kk]})
        elif gv != wv:
            out.append({'group': name, 'field': k, 'expected': wv, 'actual': gv})
    return out


def verify(descriptor: Mapping, spec_path: str = SPEC_PATH) -> dict:
    """Compare a run descriptor against the frozen identity.

    The result always carries `label`. Only a clean match gets CONFIRMED.
    """
    spec, spec_sha = load_spec(spec_path)
    if not isinstance(descriptor, Mapping):
        return {'label': REFUSED, 'code': 'DESCRIPTOR_NOT_A_MAPPING',
                'spec_sha256': spec_sha,
                'detail': f'{type(descriptor).__name__} is not a descriptor'}

    missing = [g for g in REQUIRED_GROUPS if g not in descriptor]
    if missing:
        return {'label': REFUSED, 'code': 'DESCRIPTOR_INCOMPLETE',
                'spec_sha256': spec_sha, 'missing_groups': missing,
                'detail': ('a run that does not declare a component has not '
                           'matched it. Silence is refused, not accepted.')}

    seasons = descriptor.get('consumed_seasons')
    try:
        seasons = [int(s) for s in seasons]
    except (TypeError, ValueError):
        return {'label': REFUSED, 'code': 'CONSUMED_SEASONS_MALFORMED',
                'spec_sha256': spec_sha, 'actual': descriptor.get('consumed_seasons')}
    bad = sorted(set(s for s in seasons if s in FORBIDDEN_SEASONS))
    if bad:
        return {'label': REFUSED, 'code': 'FORBIDDEN_SEASON_CONSUMED',
                'spec_sha256': spec_sha, 'seasons': bad,
                'detail': (f'{bad} outcomes are forbidden. A run that consumed '
                           f'them is refused outright -- it is not merely a '
                           f'different generation, it is not admissible.')}

    # `.get(g, {})` rather than `descriptor[g]`: an undeclared group must be
    # reported as undeclared, never raise. The completeness check above already
    # refuses this case, but a gate whose behaviour depends on another guard
    # having run first is a gate with a hole in it.
    mism = []
    mism += _cmp_map('derived_artifacts',
                     {k: v['sha256'] for k, v in spec['derived_artifacts'].items()},
                     descriptor.get('derived_artifacts', {}))
    mism += _cmp_map('leaf_inputs', spec['leaf_inputs'],
                     descriptor.get('leaf_inputs', {}))
    mism += _cmp_map('source_code', spec['source_code'],
                     descriptor.get('source_code', {}))
    mism += _cmp_map('panel_identity', spec['panel_identity'],
                     descriptor.get('panel_identity', {}))
    mism += _cmp_map('dtype_contract', spec['dtype_contract'],
                     descriptor.get('dtype_contract', {}))
    mism += _cmp_map('seed_protocol', spec['seed_protocol'],
                     descriptor.get('seed_protocol', {}))
    mism += _cmp_map('draw_protocol', spec['draw_protocol'],
                     descriptor.get('draw_protocol', {}))
    mism += _cmp_map('solver', spec['solver'], descriptor.get('solver', {}))
    fs_want, fs_got = spec['feature_set'], descriptor.get('feature_set')
    if fs_got != fs_want:
        mism.append({'group': 'feature_set', 'field': '*',
                     'expected': fs_want, 'actual': fs_got})

    if mism:
        return {'label': DIFFERENT, 'code': 'IDENTITY_MISMATCH',
                'spec_sha256': spec_sha, 'n_mismatches': len(mism),
                'mismatches': mism[:40],
                'detail': ('this is a different input generation. It may be a '
                           'perfectly good experiment; it is not the frozen '
                           'one, and it may not carry the frozen label.')}
    return {'label': CONFIRMED, 'code': 'IDENTITY_MATCHED',
            'spec_sha256': spec_sha, 'n_mismatches': 0,
            'not_promoted': True,
            'detail': ('identity matches the frozen candidate. This confirms '
                       'WHICH experiment ran; it is not by itself evidence '
                       'about the candidate, and it does not promote it.')}


def describe_files(mapping: Mapping[str, str]) -> dict:
    """Hash a {name: path} map, refusing anything absent. Fail closed."""
    out = {}
    for name, path in mapping.items():
        if not os.path.exists(path):
            raise IdentityError(f'INPUT_ABSENT: {name} -> {path}')
        if os.path.getsize(path) == 0:
            raise IdentityError(f'INPUT_EMPTY: {name} -> {path}')
        out[name] = sha256_file(path)
    return out
