"""The OAS1 design matrix, and the rank report that must precede any fit.

THE ORDER MATTERS AND IT IS ENFORCED, NOT ADVISED. `identify()` is called
before `fit()` and `fit()` refuses a structurally unidentified design unless
the caller passes `allow_unidentified=True` and says why. Ridge will always
return numbers; the entire point of this module is that it must not return
them silently on a design where the data cannot separate offense from
opponent defence.

TWO STRUCTURAL REDUNDANCIES, NOT ONE. Every play has exactly one offense and
exactly one defence, so both dummy families sum to 1 on every row and each is
collinear with the intercept. Measured on the full 2025 regular season pass
frame: 66 columns, rank 64. Dropping the intercept removes one redundancy; the
second survives because the families are then collinear with each other. So
`EXPECTED_STRUCTURAL_DEFICIENCY = 2` is the identified state, and anything
above it is unestimable opponent structure.

SIGN CONVENTION, FIXED ONCE AND ASSERTED IN A TEST

    positive alpha  = a BETTER offense
    positive delta  = a WORSE defence

because delta enters as an additive contribution to the offense's EPA. A sign
error here is the single most likely silent defect in the build, which is why
it is written here and tested rather than left to a reader's inference.
"""
from __future__ import annotations

import collections
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.ingest import allowlist as AL                              # noqa: E402

SPEC_VERSION = 'oas1-design-1'

EXPECTED_STRUCTURAL_DEFICIENCY = 2

SIGN_CONVENTION = ('positive offensive strength = better offense; '
                   'positive defensive strength = WORSE defence, because it '
                   'enters as an additive contribution to offensive EPA')

CODE_OK = 'OAS1_DESIGN_BUILT'
CODE_IDENTIFIED = 'OAS1_DESIGN_IDENTIFIED'
CODE_UNIDENTIFIED = 'OAS1_DESIGN_UNIDENTIFIED'
CODE_EPA_FEATURE = 'OAS1_EPA_IN_FEATURES'
CODE_NO_ROWS = 'OAS1_DESIGN_EMPTY'


def feature_names(teams) -> list:
    """The column names, so the target-not-feature check has something to read.

    Names are what `assert_no_epa_in_features` inspects. A design whose
    columns are anonymous cannot be audited for what went into it.
    """
    return (['intercept']
            + [f'off_{t}' for t in teams]
            + [f'def_{t}' for t in teams]
            + ['offense_is_home'])


def build(rows, *, play_class: str) -> Outcome:
    """Rows of one play class -> (X, names, teams). No target is read here."""
    sub = [r for r in rows if r.get('play_class') == play_class
           and r.get('excluded_reason') == 'none'
           and r.get('offense_team') and r.get('defense_team')]
    if not sub:
        return Outcome.fail(
            CODE_NO_ROWS, f'no kept {play_class} rows', play_class=play_class)
    teams = sorted({r['offense_team'] for r in sub}
                   | {r['defense_team'] for r in sub})
    names = feature_names(teams)
    # THE GATE THAT KEEPS THE EXEMPTION NARROW. The design is checked for
    # epa-derived columns by NAME, before it is used for anything.
    gate = AL.assert_no_epa_in_features(names)
    if gate.state is not State.PASS:
        return Outcome.fail(
            CODE_EPA_FEATURE,
            f'the design matrix contains the target: {gate.detail}',
            cause=Cause.GOVERNANCE, offending=gate.evidence.get('offending'))
    ti = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    X = np.zeros((len(sub), 1 + 2 * n + 1), dtype=np.float64)
    for k, r in enumerate(sub):
        X[k, 0] = 1.0
        X[k, 1 + ti[r['offense_team']]] = 1.0
        X[k, 1 + n + ti[r['defense_team']]] = 1.0
        X[k, 1 + 2 * n] = 1.0 if r['offense_is_home'] else 0.0
    return Outcome.ok(
        CODE_OK, value={'X': X, 'names': names, 'teams': teams, 'rows': sub},
        detail=f'{play_class}: {X.shape[0]} row(s) x {X.shape[1]} column(s), '
               f'{n} club(s)',
        spec_version=SPEC_VERSION, play_class=play_class,
        n_rows=int(X.shape[0]), n_cols=int(X.shape[1]), n_teams=n,
        feature_names_checked=True, sign_convention=SIGN_CONVENTION)


def components(rows, *, play_class: str) -> list:
    """Connected components of the offense-unit / defence-unit bipartite graph.

    This is what distinguishes UNIDENTIFIED from IMPRECISE. Inside a component
    containing one offense and one defence, only their SUM is estimable.
    """
    adj = collections.defaultdict(set)
    for r in rows:
        if r.get('play_class') != play_class or \
                r.get('excluded_reason') != 'none':
            continue
        o, d = r.get('offense_team'), r.get('defense_team')
        if not o or not d:
            continue
        adj[('O', o)].add(('D', d))
        adj[('D', d)].add(('O', o))
    seen, comps = set(), []
    for node in list(adj):
        if node in seen:
            continue
        stack, comp = [node], set()
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            seen.add(x)
            stack.extend(adj[x] - comp)
        comps.append(comp)
    return comps


def identify(rows, *, play_class: str) -> Outcome:
    """The rank report. Must be run and read BEFORE a fit is attempted.

    Returns PASS only when the deficiency equals the structural 2. Anything
    more is BLOCKED with the unestimable dimension count named, because a
    ridge fit on such a design reports the penalty's choices as opponent
    quality.
    """
    d = build(rows, play_class=play_class)
    if d.state is not State.PASS:
        return d
    X = d.value['X']
    rank = int(np.linalg.matrix_rank(X))
    cols = int(X.shape[1])
    deficiency = cols - rank
    comps = components(rows, play_class=play_class)
    sizes = collections.Counter(len(c) for c in comps)
    unestimable = deficiency - EXPECTED_STRUCTURAL_DEFICIENCY
    ev = {'spec_version': SPEC_VERSION, 'play_class': play_class,
          'n_rows': int(X.shape[0]), 'design_cols': cols, 'rank': rank,
          'deficiency': deficiency,
          'structural_deficiency': EXPECTED_STRUCTURAL_DEFICIENCY,
          'unestimable_opponent_dimensions': unestimable,
          'n_components': len(comps),
          'component_sizes': dict(sizes),
          'largest_component': max(sizes) if sizes else 0,
          'n_teams': d.evidence['n_teams'],
          'identified': deficiency == EXPECTED_STRUCTURAL_DEFICIENCY,
          'structural_redundancy_note':
              'both dummy families sum to 1 on every row, so each is '
              'collinear with the intercept: 2 redundancies, not 1'}
    if deficiency != EXPECTED_STRUCTURAL_DEFICIENCY:
        return Outcome.blocked(
            CODE_UNIDENTIFIED,
            f'{play_class}: {cols} design column(s), rank {rank}, deficiency '
            f'{deficiency}. {unestimable} dimension(s) beyond the structural '
            f'{EXPECTED_STRUCTURAL_DEFICIENCY} are UNESTIMABLE from this '
            f'design -- the offense/defence graph has {len(comps)} component(s) '
            f'with sizes {dict(sizes)}, and within a component only the SUM of '
            f'one offense and one defence carries information. A ridge fit '
            f'here returns the penalty`s choices, not opponent quality.',
            cause=Cause.DATA, **ev)
    return Outcome.ok(
        CODE_IDENTIFIED, value=dict(ev),
        detail=f'{play_class}: {cols} column(s), rank {rank}, deficiency '
               f'{deficiency} (structural), {len(comps)} graph component(s)',
        **ev)
