"""Kicking from the same simulated worlds as the offense. Two models, not one.

THE SEPARATION THAT MATTERS, and it is the reason a single career FG% is wrong:

    OPPORTUNITY   how many field goals and extra points the GAME offers, which
                  is an offense/game-script quantity and has nothing to do with
                  who is kicking
    CONVERSION    whether THIS kicker makes THIS distance, which is a kicker
                  quantity and must be estimated per distance band

Collapsing them into one number per kicker prices a 26-yard attempt and a
54-yard attempt identically. Measured over 5,639 attempts, 2021 through 2026
week 1, strictly before ordinal 202602:

    FG<20   12/12      1.0000  (n=12, no kicker has enough for a kicker term)
    FG20s   1207/1231  0.9805
    FG30s   1473/1575  0.9352
    FG40s   1259/1577  0.7984
    FG50+   857/1244   0.6889
    XP      6180/6502  0.9505

OPPORTUNITY IS COUPLED TO GAME SCRIPT BY MEASUREMENT, NOT BY ASSERTION.
A drive that ends in a touchdown does not also produce a field goal, so field
goal attempts FALL as offensive touchdowns rise. Over 2,868 team-games:

    offensive TD   0     1     2     3     4     5     6
    mean FGA     2.237 2.282 2.108 1.839 1.631 1.360 0.967

So attempts are drawn conditional on the SAME DRAW's offensive touchdowns,
which come from the same simulated worlds the receivers and backs were scored
in. A high-scoring world gives its kicker extra points and few field goals; a
stalling world gives him the opposite. Nothing is reconciled afterwards.

NO PARAMETRIC FORM IS INVENTED. Attempts are resampled from the EMPIRICAL
conditional distribution of FGA (and XPA) given that touchdown count. The
conditional standard deviation is below the mean at every touchdown count, so a
Poisson would be visibly over-dispersed; rather than pick a two-parameter
family to patch that, the observed distribution is used directly.

THE KICKER TERM IS SHRUNK, AND THE STRENGTH IS ESTIMATED, NOT CHOSEN. Per
band, k = p(1-p)/between-kicker variance, with between = observed variance
minus the binomial component -- empirical Bayes over kickers with at least 20
attempts in that band. Measured k: 20s 204.9, 30s 196.1, 40s 93.2, 50+ 164.0.
The 40s band shrinks least because kickers genuinely differ most there.

FANTASYCRUNCHER IS SCHEMA AND VALIDATION EVIDENCE ONLY, NEVER AN INPUT.
Its historical rows are what established that the professional surface is
made/attempted BY DISTANCE BAND plus XP rather than a points total, which is
the shape emitted here. As a cross-check its Bates note says he was perfect
inside 40 and that five of seven misses came from 50+; this module's
independent extraction gives Bates 11/11 in the 20s, 18/18 in the 30s and
10/17 at 50+, which is seven misses. No FC projection is read, copied or
targeted -- one visible FC 2026 row carries Proj 0.00 against real production.
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

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

SPEC_VERSION = 'kicking-opportunity-conversion-1'
BANDS = ((0, 20, 'FG<20'), (20, 30, 'FG20s'), (30, 40, 'FG30s'),
         (40, 50, 'FG40s'), (50, 99, 'FG50+'))
BAND_NAMES = tuple(b for _, _, b in BANDS)
MIN_FOR_EB = 20

#: NO SCORING TABLE LIVES HERE. This module simulated kicks AND carried its
#: own copy of the DraftKings point values, which made two answers to one
#: question -- and they had already diverged, because the points were scored
#: from an extra-point draw the caller never saw. `nfl.product.dk_scoring`
#: owns every point value; this module publishes events only, so a scoring
#: change cannot reach a simulated kick.

_CACHE: dict = {}


def _band(d):
    for lo, hi, n in BANDS:
        if lo <= d < hi:
            return n
    return None


def _cut_ok(season, week, cut_ordinal):
    try:
        return int(season) * 100 + int(week) < cut_ordinal
    except (TypeError, ValueError):
        return False


def fit(cut_ordinal: int) -> Outcome:
    """Fit both models from play-by-play strictly before `cut_ordinal`."""
    key = ('fit', cut_ordinal)
    if key in _CACHE:
        return _CACHE[key]
    files = sorted(glob.glob(str(_REPO / 'nfl/research/postgame/pbp_20*.csv.gz')))
    if not files:
        return Outcome.blocked(
            'KICKING_PBP_ABSENT',
            'no play-by-play under nfl/research/postgame, so neither the '
            'distance bands nor the opportunity table can be fitted.',
            cause=Cause.DATA)

    lg = collections.Counter()
    per = collections.defaultdict(collections.Counter)
    names: dict = {}
    tg = collections.defaultdict(lambda: {'td': 0, 'fga': 0, 'xpa': 0})
    xpa = xpm = 0
    mix = collections.Counter()
    for f in files:
        for r in csv.DictReader(gzip.open(f, 'rt')):
            if not _cut_ok(r.get('season'), r.get('week'), cut_ordinal):
                continue
            t, g = r.get('posteam'), r.get('game_id')
            if t and g:
                d = tg[(g, t)]
                if str(r.get('pass_touchdown') or '0') in ('1', '1.0'):
                    d['td'] += 1
                if str(r.get('rush_touchdown') or '0') in ('1', '1.0'):
                    d['td'] += 1
            fgr = (r.get('field_goal_result') or '').strip()
            if fgr in ('made', 'missed', 'blocked'):
                if t and g:
                    tg[(g, t)]['fga'] += 1
                try:
                    kd = float(r.get('kick_distance') or 0)
                except (TypeError, ValueError):
                    kd = 0.0
                b = _band(kd)
                if b:
                    made = 1 if fgr == 'made' else 0
                    lg[b + '_a'] += 1
                    lg[b + '_m'] += made
                    mix[b] += 1
                    # THE KEY IS THE PLAYER ID, NOT THE PRINTED NAME.
                    # pbp writes the kicker as "T.Bass" and the roster writes
                    # "Tyler Bass". Bridging those by reconstructing an
                    # initial is a guess that fails on a suffix, a hyphen or
                    # two kickers sharing a surname, and it fails SILENTLY --
                    # an unmatched kicker falls back to the league rate and
                    # nothing says so. `kicker_player_id` is the same gsis_id
                    # the roster carries, so no bridge is needed.
                    k = (r.get('kicker_player_id') or '').strip()
                    if k:
                        per[k][b + '_a'] += 1
                        per[k][b + '_m'] += made
                        nm = (r.get('kicker_player_name') or '').strip()
                        if nm:
                            names[k] = nm
            xpr = (r.get('extra_point_result') or '').strip()
            if xpr in ('good', 'failed', 'blocked'):
                xpa += 1
                xpm += 1 if xpr == 'good' else 0
                if t and g:
                    tg[(g, t)]['xpa'] += 1

    if not lg or not tg:
        return Outcome.blocked(
            'KICKING_FIT_EMPTY',
            f'no kicking rows earlier than ordinal {cut_ordinal}. Zero rows '
            f'is an absence, not a league that kicks no field goals.',
            cause=Cause.DATA, cut_ordinal=cut_ordinal)

    # LEAGUE BAND RATES, JEFFREYS. FG<20 is 12/12; carrying 1.0000 would assert
    # a 19-yard kick cannot be missed, which 12 attempts cannot establish.
    band_p, band_n = {}, {}
    for b in BAND_NAMES:
        a, m = lg[b + '_a'], lg[b + '_m']
        band_n[b] = a
        band_p[b] = ((m + 0.5) / (a + 1.0)) if a else None

    # EMPIRICAL BAYES STRENGTH PER BAND.
    kstr = {}
    for b in BAND_NAMES:
        p = band_p[b]
        elig = [(per[k][b + '_m'], per[k][b + '_a']) for k in per
                if per[k][b + '_a'] >= MIN_FOR_EB]
        if p is None or len(elig) < 5:
            kstr[b] = None
            continue
        rates = [m / a for m, a in elig]
        mu = sum(rates) / len(rates)
        obs = sum((x - mu) ** 2 for x in rates) / len(rates)
        nbar = sum(a for _, a in elig) / len(elig)
        between = max(obs - p * (1 - p) / nbar, 1e-9)
        kstr[b] = p * (1 - p) / between

    # OPPORTUNITY: the empirical conditional distributions, not a fitted form.
    fga_by_td, xpa_by_td = collections.defaultdict(list), \
        collections.defaultdict(list)
    for d in tg.values():
        fga_by_td[min(d['td'], 6)].append(d['fga'])
        xpa_by_td[min(d['td'], 6)].append(d['xpa'])

    total_mix = sum(mix.values()) or 1
    doc = {
        'spec_version': SPEC_VERSION, 'cut_ordinal': cut_ordinal,
        'band_p': band_p, 'band_n': band_n, 'eb_strength': kstr,
        'xp_p': (xpm + 0.5) / (xpa + 1.0) if xpa else None,
        'xp_n': xpa,
        'distance_mix': {b: mix[b] / total_mix for b in BAND_NAMES},
        'fga_by_td': {k: v for k, v in fga_by_td.items()},
        'xpa_by_td': {k: v for k, v in xpa_by_td.items()},
        'kicker_counts': {k: dict(v) for k, v in per.items()},
        'kicker_key': 'gsis_id',
        'kicker_names': dict(names),
        'n_team_games': len(tg), 'n_fg_attempts': sum(band_n.values()),
        'sources': [str(pathlib.Path(f).relative_to(_REPO)) for f in files],
    }
    out = Outcome.ok('KICKING_FIT_OK', value=doc, spec_version=SPEC_VERSION,
                     n_fg_attempts=doc['n_fg_attempts'],
                     n_team_games=len(tg), cut_ordinal=cut_ordinal)
    _CACHE[key] = out
    return out


def kicker_band_rates(doc, kicker_name):
    """Shrunk make probability per band for one kicker, with its basis."""
    rows = {}
    counts = (doc['kicker_counts'].get(kicker_name) or {})
    for b in BAND_NAMES:
        p = doc['band_p'][b]
        k = doc['eb_strength'][b]
        a = counts.get(b + '_a', 0)
        m = counts.get(b + '_m', 0)
        if p is None:
            rows[b] = {'p': None, 'basis': 'NO_LEAGUE_DATA', 'own': f'{m}/{a}'}
        elif k is None:
            rows[b] = {'p': p, 'basis': 'LEAGUE_ONLY_TOO_FEW_KICKERS_FOR_EB',
                       'own': f'{m}/{a}'}
        else:
            rows[b] = {'p': (m + k * p) / (a + k), 'basis': 'SHRUNK',
                       'own': f'{m}/{a}', 'k': k, 'league_p': p}
    return rows


def simulate(doc, kicker_name, team_td_draws, seed=20260908):
    """Kick the SAME worlds the offense was scored in.

    `team_td_draws` is that team's offensive touchdowns per draw, taken from
    the sealed player draws. Opportunity is conditioned on it draw by draw, so
    the coupling is structural rather than a correlation imposed afterwards.
    """
    rng = np.random.default_rng(seed)
    td = np.asarray(team_td_draws).astype(int)
    n = td.shape[0]
    rates = kicker_band_rates(doc, kicker_name)
    mix = np.array([doc['distance_mix'][b] for b in BAND_NAMES], dtype=float)
    mix = mix / mix.sum()
    xp_p = doc['xp_p']

    fga = np.zeros(n, dtype=int)
    xpa = np.zeros(n, dtype=int)
    for i in range(n):
        key = int(min(td[i], 6))
        pool = doc['fga_by_td'].get(key) or doc['fga_by_td'].get(
            min(doc['fga_by_td'], key=lambda z: abs(z - key)))
        fga[i] = pool[rng.integers(len(pool))]
        xpool = doc['xpa_by_td'].get(key) or [0]
        # XP OPPORTUNITY IS BOUNDED BY THE TOUCHDOWNS THIS DRAW ACTUALLY HAD.
        # The historical row is resampled for the two-point and defensive-score
        # texture, then clipped: a world with two offensive touchdowns cannot
        # offer four extra points.
        xpa[i] = min(int(xpool[rng.integers(len(xpool))]), int(td[i]))

    by_band_a = {b: np.zeros(n, dtype=int) for b in BAND_NAMES}
    by_band_m = {b: np.zeros(n, dtype=int) for b in BAND_NAMES}
    fgm = np.zeros(n, dtype=int)
    xpm = np.zeros(n, dtype=int)
    for i in range(n):
        if fga[i] > 0:
            drawn = rng.multinomial(int(fga[i]), mix)
            for j, b in enumerate(BAND_NAMES):
                a = int(drawn[j])
                if not a:
                    continue
                by_band_a[b][i] = a
                p = rates[b]['p']
                mk = int(rng.binomial(a, p)) if p is not None else 0
                by_band_m[b][i] = mk
                fgm[i] += mk
        # ONE DRAW, ONE PUBLISHED VALUE. This vector used to be drawn here
        # to score the points and then drawn a SECOND time from a fresh rng
        # for the return value, so the extra points a reader could see were
        # not the ones the total was built from. Scoring now lives entirely
        # in dk_scoring, which is the single definition of a DraftKings
        # point, and this module publishes only the events.
        xpm[i] = int(rng.binomial(int(xpa[i]), xp_p)) if xpa[i] > 0 else 0
    return {'fga': fga, 'fgm': fgm, 'xpa': xpa, 'xpm': xpm,
            'band_att': by_band_a, 'band_made': by_band_m,
            'rates': rates}


def resolve_kicker(doc, team: str, season: int, week: int) -> Outcome:
    """Which player kicks for `team`, from the roster capture. Never guessed.

    The first version of the board named the two kickers by hand. That is
    fine for one game and wrong for a slate: it cannot be audited, it cannot
    scale, and it silently survives a kicker being cut. This reads the roster
    capture and refuses when the answer is not there.

    THE GRADED PARTICIPATION CLASSES APPLY HERE TOO. A club can carry more
    than one player at position K -- an injured incumbent on reserve, a
    practice-squad leg. Picking the first row would sometimes pick the one
    who is not going to kick, so rows are classified and only the game-roster
    classes are eligible. If that leaves more than one, this refuses rather
    than choosing: two eligible kickers is a fact about the roster, and
    inventing a tiebreak here would bury it.
    """
    by_week = {}
    for f in sorted(glob.glob(str(
            _REPO / 'nfl/vintage/weekly_rosters.*raw.csv*'))):
        for r in csv.DictReader(gzip.open(f, 'rt')):
            if (r.get('position') or '').upper() != 'K':
                continue
            if (r.get('team') or '').strip() != team:
                continue
            try:
                if int(r.get('season') or 0) != int(season):
                    continue
                w = int(r.get('week') or 0)
            except ValueError:
                continue
            if w <= int(week):
                by_week.setdefault(w, []).append(r)
    if not by_week:
        return Outcome.blocked(
            'KICKER_NOT_ON_ROSTER_CAPTURE',
            f'no position-K row for {team} at or before {season} week '
            f'{week}. A kicker named from memory is not evidence, so no '
            f'kicking line is produced for this club.',
            cause=Cause.DATA, team=team)

    # THE MOST RECENT CAPTURE AT OR BEFORE THE FORECAST WEEK, AND IT SAYS SO.
    #
    # There is no week-2 roster capture, and a week-1 row is evidence that
    # this player was the kicker IN WEEK 1 -- not that he is the kicker now.
    # Carrying it forward is the right call for a position that turns over
    # rarely, and presenting it as current would be the "a data label is
    # football reality" error: a kicker can be cut on Tuesday and this file
    # would never know.
    #
    # So the row is used AND the basis is stamped. A reader can tell a
    # confirmed week from a carried-forward one, which is the whole point of
    # the graded classes: ACTIVE_ROSTER_EXPECTED is not
    # ACTIVE_ROSTER_CONFIRMED and this is exactly where the difference lives.
    src_week = max(by_week)
    rows = by_week[src_week]
    carried = int(src_week) != int(week)

    from nfl.production.nonqb import participant_class as PC
    graded = [(r, PC.from_roster_status(
        (r.get('status') or '').strip().upper())) for r in rows]
    classes = {(r.get('gsis_id') or ''): c for r, c in graded}

    # COUNT PLAYERS, NOT ROWS. `rows` is every position-K row for this club in
    # the source week ACROSS EVERY ROSTER VINTAGE, and the capture writes a
    # new vintage whenever the upstream file changes -- eight of them by
    # 2026-09-19. So one kicker appeared eight times and `len(eligible) != 1`
    # was true for all 32 clubs, and every board in the 2026 week-2 slate
    # rehearsal came out with no kicking line at all.
    #
    # The failure GREW WITH THE CAPTURE, which is why it was invisible when
    # written: with one or two vintages committed it resolved correctly. The
    # refusal message already carried the evidence that this was a counting
    # error -- "ATL has 7 game-roster kicker(s) ... : {'00-0025565': ...}",
    # seven kickers and one id -- and nothing read it until a full slate ran.
    #
    # The module's stated intent is unchanged and is what is now implemented:
    # two eligible KICKERS is a fact about the roster and this refuses rather
    # than choosing. Measured across all 32 clubs at 2026 week 2: exactly one
    # eligible player each.
    by_player = {}
    for r, c in graded:
        gid = (r.get('gsis_id') or '').strip()
        if not gid:
            continue
        by_player.setdefault(gid, []).append((r, c))

    # A PLAYER WHOSE VINTAGES DISAGREE ABOUT HIS ELIGIBILITY IS NOT
    # DEDUPLICATED AWAY. Collapsing the vintages would silently pick one side
    # of a real within-week roster event. It does not happen in the current
    # data -- the one raw-status conflict at 2026 week 2 is BAL's Jake Moody,
    # CUT in six vintages and DEV in one, and both grade to NOT_GAME_ROSTER --
    # so this is a refusal with no live instance, written because the
    # alternative silently loses the case it exists for.
    split = {g: sorted({PC.eligibility_state(c) for _, c in v})
             for g, v in by_player.items()}
    conflicted = {g: st for g, st in split.items() if len(st) > 1}
    if conflicted:
        return Outcome.blocked(
            'KICKER_ELIGIBILITY_DISAGREES_ACROSS_VINTAGES',
            f'{team}: {len(conflicted)} position-K player(s) grade to more '
            f'than one eligibility state within {season} week {src_week} '
            f'-- {conflicted}. That is a roster event, not a duplicate, and '
            f'picking a vintage here would bury it.',
            cause=Cause.DATA, team=team, conflicted=conflicted,
            roster_source_week=int(src_week))

    eligible_ids = [g for g, st in split.items() if st == ['ELIGIBLE']]
    if len(eligible_ids) != 1:
        return Outcome.blocked(
            'KICKER_NOT_UNIQUELY_DETERMINED',
            f'{team} has {len(eligible_ids)} game-roster kicker(s) in '
            f'{season} week {src_week}, from {len(by_player)} distinct '
            f'position-K player(s) over {len(rows)} roster-vintage row(s): '
            f'{classes}. One is required and this will not pick one.',
            cause=Cause.DATA, team=team, classes=classes,
            n_distinct_players=len(by_player), n_rows=len(rows),
            roster_source_week=int(src_week))
    row, cls = by_player[eligible_ids[0]][0]
    gsis = (row.get('gsis_id') or '').strip()
    if not gsis:
        return Outcome.blocked(
            'KICKER_HAS_NO_GSIS_ID',
            f"{team}'s kicker row carries no gsis_id, so it cannot be joined "
            f"to the fitted per-kicker counts.", cause=Cause.DATA, team=team)
    counts = (doc['kicker_counts'].get(gsis) or {})
    att = sum(v for k, v in counts.items() if k.endswith('_a'))
    basis = ('CARRIED_FORWARD_FROM_WEEK_%d_NO_CAPTURE_FOR_WEEK_%d'
             % (src_week, week)) if carried else 'ROSTER_CAPTURE_THIS_WEEK'
    return Outcome.ok(
        'KICKER_RESOLVED',
        value={'gsis_id': gsis, 'name': (row.get('full_name') or '').strip(),
               'team': team, 'participant_class': cls,
               'pbp_name': doc.get('kicker_names', {}).get(gsis),
               'prior_fg_attempts': int(att),
               'roster_basis': basis, 'roster_source_week': int(src_week)},
        spec_version=SPEC_VERSION, team=team, gsis_id=gsis,
        participant_class=cls, prior_fg_attempts=int(att),
        roster_basis=basis, roster_source_week=int(src_week),
        # A kicker with no history is NOT an error -- he shrinks all the way
        # to the league band rates, which is the right answer for a rookie.
        # It is reported because "league rates" and "his rates" are different
        # claims and a reader must be able to tell which one he is reading.
        rate_basis=('OWN_HISTORY_SHRUNK_TO_LEAGUE' if att
                    else 'LEAGUE_ONLY_NO_PRIOR_ATTEMPTS'))
