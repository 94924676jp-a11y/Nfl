"""carry -> rushing yards. System A, emp_tilt, RB vs non-RB. Owner-decided.

WHAT LIFTED THE HOLD. `layers.rushing_conversion` returned DEFERRED
RUSHING_CONVERSION_CONTROL_UNDEFINED behind three scientific decisions reserved
to the owner, and refused a caller-supplied prior BEFORE anything else so the
refusal was about ownership rather than absence. All three were decided
2026-09-16 and are recorded in RUSHING_CONVERSION_DECISIONS.json:

    family          emp_tilt, CARRIED_FORWARD_NOT_SELECTED from 2025
    system          A -- opportunity only, BLOCKS['A'] == (), no shrinkage
                    blocks for player, team or opponent
    stratification  RB versus non-RB, as predeclared

THE FAMILY IS IMPORTED, NEVER RESTATED. `p5a_lib.Pool`, `p5a_lib.tilt_pmf` and
`p5a_lib.draw_carry_yards` are the frozen definitions and this module calls
them. Re-typing an exponential tilt here would be a second answer to a question
the research module has already answered, and the two would drift.

WHY THE TILT IS AN IDENTITY UNDER SYSTEM A, AND WHY IT IS STILL APPLIED.
System A carries no shrinkage blocks, so the target mean IS the pool's own
mean and `tilt_pmf` returns the pool pmf back. It is still routed through the
frozen call rather than short-circuited, because "A happens to be an identity"
is a property of today's system list, not of the family, and a short-circuit
would silently stop being equivalent the moment a block is added.

THE STRATIFIED POOLS DID NOT EXIST AND ARE BUILT HERE. p5a_results.json carries
ONE unstratified pool per season -- 2025: mean 4.3166, p_exp 0.11415, p_stuff
0.20181 over 126,077 training carries. Decision 3 requires RB and non-RB pools,
so they are rebuilt from play-by-play strictly before the forecast ordinal.
The unstratified pool is NOT substituted for either of them.

WHAT IS PROHIBITED AND STAYS PROHIBITED. `rushing_yards = carries x
yards_per_carry`. layers.py names it: it puts a point where a distribution
belongs and discards the stuff and explosive components that make a rushing
distribution what it is. The owner's decisions do not license it, and this
module draws EVERY carry individually.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import hashlib
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p5a')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

SPEC_VERSION = 'rushing-conversion-A-emp_tilt-stratified-1'
FAMILY = 'emp_tilt'
SYSTEM = 'A'
FAMILY_LABEL = 'CARRIED_FORWARD_NOT_SELECTED'
STRATA = ('RB', 'NON_RB')
_CACHE: dict = {}


def _stratum(pos: str) -> str:
    """The predeclared split. RB and FB are the running-back stratum."""
    return 'RB' if (pos or '').upper() in ('RB', 'FB', 'HB') else 'NON_RB'


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def pools(cut_ordinal: int) -> Outcome:
    """RB and non-RB per-carry yard pools, strictly before `cut_ordinal`."""
    key = ('pools', cut_ordinal)
    if key in _CACHE:
        return _CACHE[key]
    import p5a_lib as P

    files = sorted(glob.glob(str(
        _REPO / 'nfl/research/postgame/pbp_20*.csv.gz')))
    if not files:
        return Outcome.blocked(
            'RUSHCONV_PBP_ABSENT',
            'no play-by-play under nfl/research/postgame, so no per-carry '
            'pool can be estimated.', cause=Cause.DATA)

    # POSITION COMES FROM THE ROSTER, NOT FROM THE PLAY. A rush row names the
    # rusher; it does not say what he plays. Without the bridge every carry
    # would land in one stratum, which is the unstratified pool wearing a
    # stratified name.
    # HISTORY FIRST, THEN THE CURRENT ROSTER -- AND HISTORY IS WHY.
    # The first cut resolved position from the 2026 raw roster alone and
    # DROPPED 22,821 pre-cutoff carries whose rusher is no longer rostered.
    # That is survivorship, and it was systematic by season: 9,009 carries lost
    # from 2021 against 625 from 2025, because the further back you look the
    # more of that season's rushers have left the league.
    #
    # `panel_p3` carries gsis_id and position for 2020-2025 and resolves ALL
    # 22,821 -- 20,030 of them running backs. Measured cost of the omission:
    #
    #     RB      mean 4.3896 -> 4.2902   n 42,061 -> 62,044
    #     NON_RB  mean 4.6693 -> 4.5809   n 12,580 -> 15,418
    #
    # The retained pool was biased UP about 2% because the survivors are the
    # better rushers; the stuff and explosive probabilities move by under
    # 0.005. The RB shift is -3.22 standard errors of the retained mean, so it
    # is not sampling noise. Small, systematic, and free to remove.
    # SURVIVORSHIP_AUDIT.json carries the full breakdown by season, position,
    # team, identity state, stratum and yards/carry distribution.
    #
    # PANEL FIRST, AND THE ORDER IS THE POINT. 1,102 rushers appear in both
    # bridges and 6 of them are assigned different strata -- 49 carries. The
    # panel says what the player was IN THE SEASON HE TOOK THE CARRY; the 2026
    # roster says what he is now. A historical fact takes historical evidence,
    # so the panel wins whenever both speak, not merely when the roster is
    # silent.
    pos_by_gsis = {}
    _panel = _REPO / 'nfl' / 'research' / 'inputs' / 'panel_p3.csv.gz'
    if _panel.exists():
        for r in csv.DictReader(gzip.open(_panel, 'rt')):
            g = (r.get('gsis_id') or '').strip()
            pos = (r.get('position') or '').strip()
            if g and pos and g not in pos_by_gsis:
                pos_by_gsis[g] = pos
    _n_hist = len(pos_by_gsis)
    for f in sorted(glob.glob(str(_REPO / 'nfl/vintage/weekly_rosters.*raw.csv*'))):
        for r in csv.DictReader(gzip.open(f, 'rt')):
            g = (r.get('gsis_id') or '').strip()
            if g and g not in pos_by_gsis:
                pos_by_gsis[g] = (r.get('position') or '').strip()
    if not pos_by_gsis:
        return Outcome.blocked(
            'RUSHCONV_NO_POSITION_BRIDGE',
            'no raw roster capture carries gsis_id and position, so carries '
            'cannot be split into the predeclared RB and non-RB strata. The '
            'unstratified pool is NOT substituted.', cause=Cause.DATA)

    yards = {s: [] for s in STRATA}
    unknown = 0
    for f in files:
        for r in csv.DictReader(gzip.open(f, 'rt')):
            s, w = r.get('season'), r.get('week')
            if not s or not w:
                continue
            try:
                if int(s) * 100 + int(w) >= cut_ordinal:
                    continue
            except ValueError:
                continue
            if str(r.get('rush_attempt') or '0') not in ('1', '1.0'):
                continue
            rid = (r.get('rusher_player_id') or '').strip()
            if not rid:
                continue
            pos = pos_by_gsis.get(rid)
            if pos is None:
                unknown += 1
                continue
            try:
                y = float(r.get('yards_gained') or 0)
            except (TypeError, ValueError):
                continue
            yards[_stratum(pos)].append(y)

    empty = [s for s in STRATA if len(yards[s]) < 1000]
    if empty:
        return Outcome.blocked(
            'RUSHCONV_STRATUM_TOO_THIN',
            f'{empty} carry fewer than 1000 pre-cutoff carries '
            f'({ {s: len(yards[s]) for s in STRATA} }). A pool estimated on '
            f'that is not the predeclared stratified control.',
            cause=Cause.DATA, counts={s: len(yards[s]) for s in STRATA})

    built = {}
    for s in STRATA:
        pool = P.Pool(np.asarray(yards[s], np.float32))
        # THE FROZEN CALL, not a short-circuit. Under system A the target mean
        # is the pool's own mean, so this returns the pool pmf -- but it is the
        # family's own function that says so.
        pmf = P.tilt_pmf(pool, pool.mean)
        built[s] = {'pool': pool, 'cdf': np.cumsum(pmf),
                    'n': len(yards[s]), 'mean': pool.mean,
                    'p_stuff': pool.p_stuff, 'p_exp': pool.p_exp}

    prov = {
        'spec_version': SPEC_VERSION, 'system': SYSTEM, 'family': FAMILY,
        'family_label': FAMILY_LABEL, 'cut_ordinal': cut_ordinal,
        'strata': {s: {'n_carries': built[s]['n'],
                       'mean': round(built[s]['mean'], 6),
                       'p_stuff': round(built[s]['p_stuff'], 6),
                       'p_exp': round(built[s]['p_exp'], 6)} for s in STRATA},
        'carries_with_no_position': unknown,
        'identity_sources': {'panel_p3_historical': _n_hist,
                             'total_after_roster': len(pos_by_gsis)},
        'survivorship_note': (
            'resolving position from the 2026 roster alone dropped 22,821 '
            'pre-cutoff carries, 9,009 of them from 2021 against 625 from '
            '2025. panel_p3 resolves all of them. The roster-only pools were '
            'biased up ~2% on the mean because survivors rush better.'),
        'sources': [{'path': str(pathlib.Path(f).relative_to(_REPO)),
                     'sha256': _sha(f)} for f in files],
        'audit_artifact': 'nfl/production/nonqb/SURVIVORSHIP_AUDIT.json',
        'position_precedence': 'panel_p3_historical > weekly_rosters_2026',
        'not_used': 'p5a_results.json unstratified pool',
    }
    out = Outcome.ok('RUSHCONV_POOLS_BUILT', value=built, provenance=prov,
                     spec_version=SPEC_VERSION,
                     detail=f"RB n={built['RB']['n']} mean="
                            f"{built['RB']['mean']:.4f}; NON_RB "
                            f"n={built['NON_RB']['n']} mean="
                            f"{built['NON_RB']['mean']:.4f}")
    _CACHE[key] = out
    return out


def yards_for(carries, position, built, seed, tag=''):
    """Compound draw: EVERY carry drawn individually, then summed.

    `carries` is the per-draw carry count already dealt by the conserved
    allocation -- it is consumed, never resampled, so the rushing yards belong
    to the same carries the accounting closed on.
    """
    import p5a_lib as P
    c = np.asarray(carries).astype(int)
    st = built[_stratum(position)]
    rng = np.random.default_rng(
        [int(seed), int(abs(hash(tag)) % (2 ** 31)), len(c)])
    total = int(c.sum())
    out = np.zeros(c.shape[0], dtype=np.float64)
    if total <= 0:
        return out
    flat = P.draw_carry_yards(FAMILY, st['pool'], total,
                              {'cdf': st['cdf']}, rng)
    # np.add.reduceat needs the start of each run; a zero-carry draw must get
    # zero rather than the previous draw's total.
    idx = np.concatenate([[0], np.cumsum(c)[:-1]])
    nz = c > 0
    sums = np.add.reduceat(np.asarray(flat, np.float64), idx[nz]) if nz.any() \
        else np.zeros(0)
    out[nz] = sums
    return out
