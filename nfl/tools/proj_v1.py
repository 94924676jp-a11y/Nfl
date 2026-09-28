#!/usr/bin/env python3.12
"""V1 projections. Role state constrains the prior, the prior supplies shares, team volume
supplies the level, measured rates supply touchdowns, and reconciliation is a hard constraint.

WHAT V0 DID AND WHY IT WAS BROKEN. V0 measured a player's share from the current season alone
-- two games in week three -- shrunk it toward a positional mean with a two-pseudo-game
constant, and multiplied by team volume. Four consequences, all observed:

  * an injury replacement kept his starter-level share after the starter returned, because two
    games of usage is all the model could see. Drew Lock projected 17.88 DK points as a backup.
  * an established star with a quiet fortnight was shrunk toward a positional mean, because the
    model had no memory of who he is. Ja'Marr Chase came back as a secondary receiver.
  * touchdowns came from a raw two-game red-zone count, so Tee Higgins scored EXACTLY 0.000
    expected touchdowns on twenty-six targets.
  * the club touchdown pool divided the implied total by 7.0, crediting every point to a
    touchdown and ignoring field goals, inflating every pool by about a third.

WHAT V1 DOES INSTEAD, in the order the numbers are built:

  1 ROLE STATE FIRST, as a constraint and not a description. role_state.py decides the band a
    player may be asked about, from the stronger of his history and his current usage, capped
    by what current evidence permits. The cap is applied BEFORE the prior is consulted, so the
    question "what does an alpha quarterback do" is never even asked about a backup.
  2 SHARES FROM THE HIERARCHICAL PRIOR, fitted through 2025 and queried at that band, with
    recency, role similarity and sample weighting. Six seasons of evidence, not two games.
  3 CURRENT SEASON AS EVIDENCE, NOT AS TRUTH. The 2026 weeks are combined with the prior by
    weight, so a genuine role change moves the number and a quiet fortnight does not.
  4 TEAM VOLUME from the club's own measured plays, blended across seasons and scaled by the
    market implied total. Shares are of a club, so the denominator must be that club.
  5 TOUCHDOWNS from rates MEASURED in td_rates.py, allocated inside a pass/rush split club
    pool, so player touchdowns sum to what the club is expected to score.
  6 RECONCILIATION as a hard constraint, not a diagnostic. Targets sum to team targets and so
    on down the ladder; a board that does not reconcile is rejected rather than reported.

NOTHING HERE IS FITTED ON 2026. Every rate and prior is estimated through 2025 so that the
current season can be used to test the model rather than to build it.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'proj-v1-1'
LABEL = 'PROPRIETARY_V1'

POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
ROLE = _REPO / 'nfl/derived/ROLE_STATE.json'
RATES = _REPO / 'nfl/derived/TD_RATES.json'
OUT = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'

FORECAST_SEASON = 2026
#: The prior sees nothing after this season. 2026 is the test set, not training data.
THROUGH_SEASON = 2025

#: DraftKings scoring. Read from the contest rules, not recalled.
DK = {'pass_yd': 0.04, 'pass_td': 4.0, 'int': -1.0, 'rush_yd': 0.1, 'rush_td': 6.0,
      'rec': 1.0, 'rec_yd': 0.1, 'rec_td': 6.0, 'fumble_lost': -1.0,
      'bonus_100_rush': 3.0, 'bonus_100_rec': 3.0, 'bonus_300_pass': 3.0}

#: SELECTED ON OUT-OF-SAMPLE SKILL, not declared. Cap on the effective observations the
#: multi-season prior may contribute against the current season's evidence. Swept over
#: {0, 2, 4, 8, 12, 24}, chosen on 2023-2025 and CONFIRMED on untouched 2021-2022:
#:
#:      cap    rho(sel)  rho(conf)  MAE(sel)  MAE(conf)  top30act(conf)  level(conf)
#:        0      0.6361     0.6281     5.046      5.428          18.645        1.012
#:        2      0.6298     0.6232     5.050      5.410          18.651        0.996
#:       12      0.5848     0.6027     5.239      5.490          18.574        0.981
#:     base      0.5838     0.5927     5.564      5.816          18.433        1.027
#:
#: THE DECLARED 12 THREW AWAY THE WHOLE ADVANTAGE: at 12 the model only ties a current-season-only
#: baseline on rank correlation. The finding underneath is that the multi-season prior earns its
#: place as a FALLBACK WHERE THE CURRENT SEASON IS SILENT, not as a shrinkage target for evidence
#: that exists. Blending it into a measure the current season already covers destroys information.
#:
#: 2 is chosen over 0 on best MAE and best top-30 realised points in BOTH sets, and a confirmation
#: level nearest 1.0, at a cost of 0.006 rho. It also keeps a real, small prior contribution rather
#: than the degenerate fallback-only case.
PRIOR_WEIGHT_CAP = 2.0

#: Pseudo-games of last season's team volume mixed into this season's measured volume. DECLARED:
#: two games of pace is a thin estimate and a club's offence does not reset in September.
TEAM_VOLUME_PRIOR_GAMES = 4.0

CONSTANTS_PROVENANCE = {
    'PRIOR_WEIGHT_CAP': (PRIOR_WEIGHT_CAP,
                         'SELECTED on out-of-sample skill over 42 weeks and CONFIRMED on 28 '
                         'untouched weeks. See the note at the definition. Not declared.'),
    'TEAM_VOLUME_PRIOR_GAMES': (TEAM_VOLUME_PRIOR_GAMES,
                                'DECLARED pseudo-games of prior-season club volume.'),
    'THROUGH_SEASON': (THROUGH_SEASON,
                       'Hard holdout boundary. Every prior and rate is fitted at or before '
                       'this season so 2026 can test the model.'),
    'DK': (DK, 'DraftKings classic scoring, read from contest rules.'),
}


# --------------------------------------------------------------------------- team volume
def team_volume(panel, env):
    """Per-game club volume, blended across seasons and scaled by the market implied total.

    A share is a share OF A CLUB, so the denominator has to be that club's own volume. The
    current season contributes its measured weeks, the prior season contributes declared
    pseudo-games, and the market implied total then scales the level -- a club expected to
    score more runs more plays and finishes more drives.
    """
    teams = panel['teams']
    implied = {}
    for game, e in (env or {}).items():
        if '@' not in game:
            continue
        away, home = game.split('@')
        implied[away] = e.get('away_implied')
        implied[home] = e.get('home_implied')
    known = [v for v in implied.values() if v]
    league_mean = sum(known) / len(known) if known else None

    FIELDS = ('plays', 'dropbacks', 'pass_attempts', 'rush_attempts', 'targets',
              'rz_plays', 'gl_plays', 'sacks')
    out = {}
    for club, seasons in teams.items():
        cur = seasons.get(str(FORECAST_SEASON)) or {}
        prv = seasons.get(str(FORECAST_SEASON - 1)) or {}
        n_cur = len(cur)
        if not n_cur and not prv:
            out[club] = {'state': 'NO_VOLUME_HISTORY'}
            continue
        blend = {}
        for f in FIELDS:
            c = sum((w.get(f) or 0) for w in cur.values())
            p = sum((w.get(f) or 0) for w in prv.values())
            n_prv = len(prv)
            wc, wp = float(n_cur), (TEAM_VOLUME_PRIOR_GAMES if n_prv else 0.0)
            per_cur = (c / n_cur) if n_cur else None
            per_prv = (p / n_prv) if n_prv else None
            if per_cur is None:
                blend[f] = per_prv
            elif per_prv is None:
                blend[f] = per_cur
            else:
                blend[f] = (wc * per_cur + wp * per_prv) / (wc + wp)
        imp = implied.get(club)
        # THE MARKET IS NOT APPLIED TO VOLUME, and V0 applied it twice. V0 multiplied every club's
        # plays, attempts, carries and targets by implied_total / league_mean, so Buffalo at a
        # 28.75 implied total had its pass attempts lifted from a measured 31.6 to 41.5 -- a
        # claim that a club expected to score thirty-one per cent more runs thirty-one per cent
        # more plays. That is not how scoring more works: it comes mostly from efficiency, and a
        # favoured club tends to run MORE and throw LESS as it protects a lead, so even the sign
        # is not obvious.
        #
        # The market's information about scoring already enters this model once, properly, in the
        # club touchdown pool, where expected touchdowns are regressed on the implied total over
        # 2,689 club-games. Applying it to volume as well double-counts the same signal.
        #
        # Estimating a real volume-to-implied relationship needs historical closing lines joined
        # to historical play counts. This repository holds no line history, so the coefficient
        # cannot be estimated here and is therefore NOT INVENTED. Requested in
        # docs/AGENT_OUTBOX.md as OUT-036. Until it is measured the scale is exactly 1.0 and the
        # figure V0 would have used is recorded alongside it for comparison.
        scale = 1.0
        would_have = (imp / league_mean) if (imp and league_mean) else None
        row = {'state': 'OK', 'weeks_observed_2026': n_cur,
               'weeks_observed_prior_season': len(prv),
               'implied_total': imp,
               'volume_scale_applied': 1.0,
               'volume_scale_V0_WOULD_HAVE_APPLIED': (round(would_have, 4) if would_have
                                                      else None),
               'WHY_NOT_SCALED': 'the market enters once, in the touchdown pool. See the note in '
                                 'team_volume(). Coefficient unmeasurable here: OUT-036.',
               'blend_weights': {'current_season_games': n_cur,
                                 'prior_season_pseudo_games': TEAM_VOLUME_PRIOR_GAMES}}
        for f in FIELDS:
            row[f'{f}_pg'] = round(blend[f], 4) if blend[f] is not None else None
            row[f'proj_{f}'] = (round(blend[f] * scale, 4) if blend[f] is not None else None)
        out[club] = row
    return out, implied, league_mean


# ------------------------------------------------------------------- combine prior + current
def _combine(prior_value, prior_n, cur_value, cur_n):
    """Prior and current-season evidence, by weight. Returns value and the accounting.

    UNKNOWN IS NOT ZERO on either side. A player with no prior and no current observation gets
    None and a reason, never 0.0.
    """
    pn = min(float(prior_n or 0.0), PRIOR_WEIGHT_CAP)
    cn = float(cur_n or 0.0)
    if prior_value is None and cur_value is None:
        return None, {'basis': 'NO_EVIDENCE_EITHER_SIDE'}
    if prior_value is None:
        return cur_value, {'basis': 'CURRENT_SEASON_ONLY', 'current_n': cn}
    if cur_value is None or cn <= 0:
        return prior_value, {'basis': 'PRIOR_ONLY', 'prior_n_capped': round(pn, 2)}
    tot = pn + cn
    return ((pn * prior_value + cn * cur_value) / tot,
            {'basis': 'PRIOR_AND_CURRENT', 'prior_n_capped': round(pn, 2), 'current_n': cn,
             'prior_weight_fraction': round(pn / tot, 3)})


def current_season_shares(panel, gsis, club, pos):
    """Measured 2026 shares for this player, divided by HIS OWN club's weeks. Never league."""
    seasons = (panel['players'].get(gsis) or {})
    cur = seasons.get(str(FORECAST_SEASON)) or {}
    if not cur:
        return {}, 0
    tm = (panel['teams'].get(club) or {}).get(str(FORECAST_SEASON)) or {}
    agg = collections.Counter()
    tagg = collections.Counter()
    n = 0
    for wk, w in cur.items():
        t = tm.get(wk)
        if not t:
            continue
        n += 1
        for f in ('targets', 'carries', 'pass_attempts', 'rz_targets', 'rz_carries',
                  'gl_carries', 'receptions', 'rec_yards', 'rush_yards', 'pass_yards',
                  'completions'):
            agg[f] += (w.get(f) or 0)
        for f in ('targets', 'rush_attempts', 'pass_attempts', 'rz_plays', 'gl_plays'):
            tagg[f] += (t.get(f) or 0)
    if not n:
        return {}, 0
    s = {}
    if tagg['targets']:
        s['target_share'] = agg['targets'] / tagg['targets']
        if tagg['rz_plays']:
            s['rz_target_share'] = agg['rz_targets'] / tagg['rz_plays']
    if tagg['rush_attempts']:
        s['carry_share'] = agg['carries'] / tagg['rush_attempts']
        if tagg['rz_plays']:
            s['rz_carry_share'] = agg['rz_carries'] / tagg['rz_plays']
        if tagg['gl_plays']:
            s['gl_carry_share'] = agg['gl_carries'] / tagg['gl_plays']
    if tagg['pass_attempts']:
        s['pass_attempt_share'] = agg['pass_attempts'] / tagg['pass_attempts']
    if agg['targets'] >= 2:
        s['yards_per_target'] = agg['rec_yards'] / agg['targets']
        s['catch_rate'] = agg['receptions'] / agg['targets']
    if agg['carries'] >= 3:
        s['yards_per_carry'] = agg['rush_yards'] / agg['carries']
    if agg['pass_attempts'] >= 5:
        s['yards_per_attempt'] = agg['pass_yards'] / agg['pass_attempts']
        s['completion_rate'] = agg['completions'] / agg['pass_attempts']
    return s, n


# --------------------------------------------------------------- DK yardage bonus, measured
def bonus_rates(panel, pos_of, through=None):
    """P(100+ yards) and P(300+ passing) as a function of a player's own mean, MEASURED.

    WHY THIS IS NOT A CONSTANT AND NOT OMITTED. DraftKings pays three points for a hundred
    rushing or receiving yards and for three hundred passing yards. Omitting the bonus
    under-projects every high-volume player, which is one of the complaints against V0.
    Inventing a probability would be a silent constant. So the relationship between a player's
    mean yards and how often he clears the threshold is measured over player-seasons through
    2025 and read off as a step function.
    """
    buckets = {'rec': collections.defaultdict(lambda: [0, 0]),
               'rush': collections.defaultdict(lambda: [0, 0]),
               'pass': collections.defaultdict(lambda: [0, 0])}
    EDGES = {'rec': list(range(0, 121, 10)), 'rush': list(range(0, 121, 10)),
             'pass': list(range(0, 361, 20))}

    def _b(kind, mean):
        e = EDGES[kind]
        for i in range(len(e) - 1, -1, -1):
            if mean >= e[i]:
                return e[i]
        return e[0]

    for gsis, seasons in panel['players'].items():
        if pos_of.get(gsis) not in ('QB', 'RB', 'WR', 'TE'):
            continue
        for season, weeks in seasons.items():
            if int(season) > (THROUGH_SEASON if through is None else through):
                continue
            wk = list(weeks.values())
            if len(wk) < 4:
                continue
            for kind, fld, thresh in (('rec', 'rec_yards', 100.0),
                                      ('rush', 'rush_yards', 100.0),
                                      ('pass', 'pass_yards', 300.0)):
                vals = [(w.get(fld) or 0.0) for w in wk]
                mean = sum(vals) / len(vals)
                if mean <= 0:
                    continue
                b = buckets[kind][_b(kind, mean)]
                b[0] += sum(1 for v in vals if v >= thresh)
                b[1] += len(vals)
    out = {}
    for kind, d in buckets.items():
        raw = {k: (v[0] / v[1], v[1], v[0]) for k, v in sorted(d.items()) if v[1] >= 25}
        # ENFORCED MONOTONE. Clearing a threshold cannot become less likely as a player's mean
        # rises; where the raw buckets say otherwise it is small-sample noise. Without this a
        # quarterback projected for 120 passing yards drew a SMALLER bonus than one projected
        # for 100. The running maximum is applied and both values are kept so the adjustment
        # is visible rather than silent.
        run = 0.0
        out[kind] = {}
        for k in sorted(raw):
            pr, n, hits = raw[k]
            iso = max(run, pr)
            run = iso
            out[kind][str(k)] = {'p': round(iso, 5), 'p_raw': round(pr, 5),
                                 'monotone_adjusted': iso > pr + 1e-12,
                                 'n_weeks': n, 'hits': hits}
        out[kind + '_EDGES'] = EDGES[kind]
        out[kind + '_TOP_BUCKET_CAPS'] = (
            'a player projected above the top measured bucket reads that bucket, so the very '
            'highest projections are credited a bonus probability that is if anything low.')
    out['STATE'] = 'MEASURED'
    out['NOT_MODELLED'] = {
        'fumbles_lost': 'the usage panel carries no fumble field, so the DK -1 for a lost '
                        'fumble is NOT applied. This makes every projection slightly HIGH. '
                        'Recorded rather than silently omitted; needs a fumble field in the '
                        'panel to fix.',
    }
    return out


def bonus_p(rates, kind, mean):
    """Read the measured bonus probability for this mean. Returns None when unmeasured."""
    tbl = rates.get(kind) or {}
    edges = rates.get(kind + '_EDGES') or []
    if mean is None or not tbl or not edges:
        return None
    for e in reversed(edges):
        if mean >= e and str(e) in tbl:
            return tbl[str(e)]['p']
    return None


def int_rate(panel, pos_of, through=None):
    """League interceptions per pass attempt, measured through the holdout boundary."""
    a = i = 0
    for gsis, seasons in panel['players'].items():
        if pos_of.get(gsis) != 'QB':
            continue
        for season, weeks in seasons.items():
            if int(season) > (THROUGH_SEASON if through is None else through):
                continue
            for w in weeks.values():
                a += (w.get('pass_attempts') or 0)
                i += (w.get('interceptions') or 0)
    return {'state': 'MEASURED', 'int_per_attempt': round(i / a, 6) if a else None,
            'attempts': a, 'interceptions': i}


# ------------------------------------------------------------------------------- identity
def resolve_slate_identities(post, name_ix):
    """Map every slate row to a gsis id, or record why not. Never guesses an identifier.

    FOUR IDENTITY DEFECTS IN THIS PROJECT PROMPTED THIS SHAPE. The worst had a quarterback's
    identifier used for a receiver, which returned a 0.0 target share that looked like a
    football fact. Resolution is by name, then narrowed by position and club, and anything that
    does not narrow to exactly one player is reported UNRESOLVED and treated as a cold start --
    not silently attached to the first candidate.
    """
    try:
        from nfl.tools.availability import NAME_ALIASES
    except Exception:
        NAME_ALIASES = {}
    # DECLARED NORMALISATION, not fuzzy matching. DraftKings carries generational suffixes the
    # roster feed omits: 'Anthony Richardson Sr.', 'James Cook III', 'Michael Pittman Jr.'.
    # Stripping a known suffix is a transformation of the same name; it is NOT a similarity
    # search, and nothing here matches on edit distance or on a shortened first name.
    SUFFIXES = (' Jr.', ' Jr', ' Sr.', ' Sr', ' II', ' III', ' IV', ' V')

    def _strip_suffix(n):
        for suf in SUFFIXES:
            if n.endswith(suf):
                return n[: -len(suf)].strip()
        return n

    norm_ix = {}
    for n, v in name_ix.items():
        norm_ix.setdefault(_strip_suffix(n), {}).update(v)

    res, unresolved = {}, []
    suffix_matched = []
    for dk_id, p in post['players'].items():
        nm, pos, club = p.get('name'), p.get('position'), p.get('team')
        cand = name_ix.get(nm) or {}
        how = 'EXACT_NAME'
        if not cand:
            alias = NAME_ALIASES.get((nm, club))
            if alias:
                cand = name_ix.get(alias) or {}
                how = 'DECLARED_ALIAS'
        if not cand:
            cand = norm_ix.get(_strip_suffix(nm)) or {}
            if cand:
                how = 'SUFFIX_NORMALISED'
                suffix_matched.append(nm)
        if not cand:
            unresolved.append({'dk_id': dk_id, 'name': nm, 'position': pos, 'team': club,
                               'reason': 'NAME_NOT_IN_ROSTER_BLOBS'})
            continue
        hits = list(cand.items())
        if len(hits) > 1:
            narrowed = [h for h in hits if h[1][0] == pos] or hits
            if len(narrowed) > 1:
                by_club = [h for h in narrowed if h[1][1] == club]
                narrowed = by_club or narrowed
            hits = narrowed
        if len(hits) != 1:
            unresolved.append({'dk_id': dk_id, 'name': nm, 'position': pos, 'team': club,
                               'reason': 'AMBIGUOUS_AFTER_POSITION_AND_CLUB',
                               'candidates': [h[0] for h in hits][:5]})
            continue
        g, (rpos, rclub, yr) = hits[0]
        res[dk_id] = {'gsis_id': g, 'roster_position': rpos, 'roster_team': rclub,
                      'roster_latest_season': yr, 'matched_by': how,
                      'position_agrees': rpos == pos, 'club_agrees': rclub == club}
    return res, unresolved, suffix_matched


# ------------------------------------------------------------------------------ projection
SKILL = ('QB', 'RB', 'WR', 'TE')


def _m(h, key):
    """A measure from a hierarchical prior result, or None. Never coerced to zero."""
    if not isinstance(h, dict):
        return None
    v = (h.get('measures') or {}).get(key)
    return v


def project_player(panel, gsis, pos, band, club, tv, rates, cur_shares, cur_n, prior,
                   is_predicted_starter=None, depth=None):
    """One player's share CLAIMS and efficiencies. Absolute volume is allocated per club after.

    A claim is not a projection. The prior says what fraction of a club's work this player took
    when he played; it does not know who else is on the roster this Sunday. Summing claims over
    a twenty-five man DraftKings roster over-allocated carries by 3.3x and targets by 1.8x,
    because those claims were earned alongside teammates who are now at other clubs. So claims
    are collected here and turned into volume in allocate_opportunity(), where the club total is
    satisfied by construction instead of being repaired afterwards.
    """
    out = {'position': pos, 'role_band': band, 'prior_tier': prior.get('tier'),
           'prior_confidence': prior.get('confidence'),
           'prior_effective_obs': prior.get('effective_obs_at_role'),
           'prior_seasons_used': prior.get('seasons_used'),
           'current_season_weeks': cur_n, 'basis': {}}

    def comb(key):
        v, acct = _combine(_m(prior, key), prior.get('effective_obs_at_role'),
                           cur_shares.get(key), cur_n)
        out['basis'][key] = acct
        return v

    claims = {'targets': comb('target_share'), 'carries': comb('carry_share'),
              'pass_attempts': comb('pass_attempt_share')}
    rzt_share = comb('rz_target_share')
    rzc_share = comb('rz_carry_share')
    out['efficiency'] = {'yards_per_target': comb('yards_per_target'),
                         'catch_rate': comb('catch_rate'),
                         'yards_per_carry': comb('yards_per_carry'),
                         'yards_per_attempt': comb('yards_per_attempt'),
                         'completion_rate': comb('completion_rate')}

    # APPEARANCE PROBABILITY, for the one exclusive role. A second quarterback's starter history
    # is real; what is small is the chance he takes the snaps this Sunday. The measured
    # unconditional share for a rank-2 quarterback is about two per cent against ninety-eight for
    # the starter. Without this, Justin Fields projected 17.71 DK points behind Patrick Mahomes at
    # 20.62, and the pair were allocated more pass attempts than Kansas City throws.
    if pos == 'QB' and is_predicted_starter is False and depth:
        qb = ((depth.get('QB') or {}).get('by_rank') or {}).get('rank_2') or {}
        u = qb.get('unconditional_expected_share')
        ar = qb.get('appearance_rate') or 0.0
        if u is not None:
            out['appearance_adjustment'] = {
                'applied': True, 'reason': 'NOT_PREDICTED_STARTER',
                'raw_pass_attempt_claim': (round(claims['pass_attempts'], 5)
                                           if claims['pass_attempts'] is not None else None),
                'measured_rank2_unconditional_share': u,
                'appearance_rate': qb.get('appearance_rate'),
                'conditional_share_if_he_plays': qb.get('conditional_mean_share'),
                'DECOMPOSITION': 'expected = P(appears) x E[share | appears]. His role band and '
                                 'his efficiency are NOT shrunk -- they are what he does when he '
                                 'plays. Only the probability he plays is small.'}
            claims['pass_attempts'] = (u if claims['pass_attempts'] is None
                                       else min(claims['pass_attempts'], u))
            if claims['carries'] is not None:
                claims['carries'] *= ar
            if rzc_share is not None:
                rzc_share *= ar

    # Red-zone CONCENTRATION, held as a rate against the player's own volume rather than as a
    # share of the club's red-zone plays. Expressed this way it survives reallocation: whatever
    # volume he is finally given, his red-zone mix travels with it. Taken from the prior across
    # seasons -- read from the current season alone it is two games, and the measured red-zone
    # conversion rate is seventeen times the non-red-zone rate for a receiver, so one red-zone
    # look swamps a season of volume. That is how V0 put Tee Higgins at 0.000 expected
    # touchdowns on twenty-six targets while a reserve tight end outranked him.
    T, C, RZ = tv.get('proj_targets'), tv.get('proj_rush_attempts'), tv.get('proj_rz_plays')

    def _intensity(rz_share, vol_share, club_vol):
        if not rz_share or not vol_share or not club_vol or not RZ:
            return None
        return max(0.0, min(1.0, (rz_share / vol_share) * (RZ / club_vol)))

    out['rz_intensity'] = {
        'rec': _intensity(rzt_share, claims['targets'], T),
        'rush': _intensity(rzc_share, claims['carries'], C),
        'SEMANTICS': 'red-zone opportunities per unit of his own volume, so it is invariant to '
                     'how much volume he is finally allocated.'}
    out['claims'] = {k: (round(v, 6) if v is not None else None) for k, v in claims.items()}
    out['_claims'] = claims
    return out


def group_shares(panel, pos_of, through=None):
    """Share of club targets and carries taken by each position group. MEASURED.

    Club targets do not belong to receivers alone -- tight ends take a quarter of them and backs
    a sixth. Allocating a club's targets within one position group and ignoring the others would
    either over-feed receivers or leave the identity unsatisfiable.
    """
    acc = {'targets': collections.Counter(), 'carries': collections.Counter()}
    for g, seasons in panel['players'].items():
        pos = pos_of.get(g)
        if pos not in SKILL:
            continue
        for season, weeks in seasons.items():
            if int(season) > (THROUGH_SEASON if through is None else through):
                continue
            for w in weeks.values():
                if not w.get('team'):
                    continue
                acc['targets'][pos] += (w.get('targets') or 0)
                acc['carries'][pos] += (w.get('carries') or 0)
    out = {}
    for f, c in acc.items():
        tot = sum(c.values()) or 1
        out[f] = {p: round(v / tot, 6) for p, v in c.items()}
        out[f + '_total_observed'] = int(tot)
    out['state'] = 'MEASURED'
    return out


#: SELECTED ON OUT-OF-SAMPLE SKILL, not declared. Weight on the player's own claim against the
#: measured depth curve for his rank, as a geometric mean. Swept over {0, 0.25, 0.5, 0.75, 1.0} by
#: forward_chain.py, chosen on 2023-2025 (42 weeks) and CONFIRMED on untouched 2021-2022 (28
#: weeks), paired by week:
#:
#:      blend   rho(sel)  rho(conf)  MAE(sel)  MAE(conf)  level(conf)
#:      0.00     0.5142     0.5551     6.125      6.176        1.032
#:      0.50     0.5659     0.5860     5.539      5.782        1.020
#:      1.00     0.6298     0.6232     5.050      5.410        0.996
#:
#: Monotone on every metric in both sets. The declared 0.5 was measurably worse: using the depth
#: curve as a SHRINKAGE TARGET for evidence that exists destroys discrimination, which is the same
#: error V0 made by shrinking toward a positional mean. At 1.0 the measured depth and group-split
#: curves still do their work, but only through the thin-evidence branch below, where a player has
#: a claim on one side and nothing on the other.
DEPTH_CLAIM_BLEND = 1.0

CONSTANTS_PROVENANCE['DEPTH_CLAIM_BLEND'] = (
    DEPTH_CLAIM_BLEND,
    'SELECTED on out-of-sample skill over 42 weeks and CONFIRMED on 28 untouched weeks. See the '
    'note at the definition. Not declared.')

#: Role bands, strongest first, for ordering depth rank. Mirrors role_state's ladder.
BANDS_ORDER = {'ALPHA': 5, 'PRIMARY': 4, 'SECONDARY': 3, 'ROTATIONAL': 2, 'FRINGE': 1}


def allocate_opportunity(crows, tv, depth, groups, blend=None):
    """Turn share claims into volume, satisfying every club identity by construction.

    ONE POOL PER FIELD, NOT ONE POOL PER POSITION GROUP. Two measured ingredients and one
    declared one:

      * GROUP SPLIT and DEPTH CONCENTRATION, both measured, combine into each player's PRIOR
        EXPECTED share of the club total: a club's carries go 78 per cent to its backs and 19 to
        its quarterback, and within the back room the first man takes 0.78 of it.
      * The player's own CLAIM from the hierarchical prior.
      * The BLEND of the two, declared.

    Allocating group by group made the group split a league constant that no player could move,
    so every pocket passer inherited a runner's carries -- Jared Goff came out at 5.0 rushes a
    game. Weighting one club-wide pool lets a quarterback who does not run surrender his share to
    the backs, while the measured split still governs where the evidence is thin.

    Weights are normalised across the whole club, so targets sum to club targets exactly.
    Reconciliation stops being a repair and becomes an identity.
    """
    acct = {}
    for field, teamfld in (('targets', 'proj_targets'), ('carries', 'proj_rush_attempts'),
                           ('pass_attempts', 'proj_pass_attempts')):
        team_total = tv.get(teamfld)
        if team_total is None:
            acct[field] = {'state': 'CLUB_TOTAL_UNKNOWN'}
            continue
        gs = ({'QB': 1.0} if field == 'pass_attempts'
              else (groups.get('targets' if field == 'targets' else 'carries') or {}))
        # rank inside each position group, then read the measured depth share for that rank
        dvals, claims = [0.0] * len(crows), []
        for i, r in enumerate(crows):
            claims.append(max(0.0, (r.get('_claims') or {}).get(field) or 0.0))
        appear = [1.0] * len(crows)
        for pos in SKILL:
            idx = [i for i, r in enumerate(crows) if r['position'] == pos]
            if not idx or not gs.get(pos):
                continue
            # DEPTH RANK IS ORDERED BY CURRENT ROLE EVIDENCE FIRST, THEN BY CLAIM SIZE.
            # Ranking by claim alone let a veteran's history outrank the man who actually
            # starts: David Njoku came out at 1.571x Oronde Gadsden II, the predicted starting
            # tight end, because Njoku's multi-season claim is larger. That is the Drew Lock
            # error in the allocator rather than in the prior -- history beating current role
            # designation -- and it is the ordering, not the threshold, that was wrong. The
            # predicted starter takes rank 1; a good player behind him keeps a large claim
            # inside rank 2, which is what a quality backup should look like.
            idx.sort(key=lambda i: (0 if crows[i].get('is_predicted_starter') else 1,
                                    -BANDS_ORDER.get(crows[i].get('role_band'), 0),
                                    -claims[i]))
            dr = ((depth.get(pos) or {}).get('by_rank') or {})
            # A RANK DEEPER THAN THE MEASURED TABLE INHERITS THE DEEPEST MEASURED RANK, NEVER 1.0.
            # The depth table is measured over players who appeared, so it runs a handful of ranks
            # deep. A DraftKings roster runs to twenty-five, and defaulting a missing rank's
            # appearance probability to 1.0 declared a club's eighth receiver certain to play and
            # let him take volume from the starters -- it drove the scored level down to 0.79.
            # Falling back to the deepest measured rank is the conservative direction and the only
            # one consistent with the curve's shape.
            _ranks = sorted(int(k.split('_')[1]) for k in dr)
            _deepest = dr.get(f'rank_{_ranks[-1]}') if _ranks else {}
            for rank, i in enumerate(idx, start=1):
                row = dr.get(f'rank_{rank}') or _deepest or {}
                beyond = f'rank_{rank}' not in dr
                dvals[i] = gs[pos] * (row.get('unconditional_expected_share') or 0.0)
                # APPEARANCE PROBABILITY FOR EVERY POSITION, not only quarterback. A claim is
                # what a player takes WHEN HE PLAYS; expected production is P(plays) times that.
                # The measured appearance rate by depth rank supplies P(plays).
                #
                # WHY THIS WAS MISSING AND WHY THE FORWARD CHAIN COULD NOT FIND IT. The chain's
                # universe is players who APPEARED in the scored week -- about ten per club -- so
                # every appearance probability there is 1 and the term is invisible. A DraftKings
                # roster carries about twenty-five per club, most of whom will not play. Dividing
                # a club's targets among twenty-five claims instead of among the ten who play
                # collapsed every star: Ja'Marr Chase came out at 10.57 DK points against an
                # external 27.08, while quarterbacks were unaffected because a starter's
                # pass-attempt claim is near 1.0 and the allocation barely touches him.
                #
                # The depth curve at a mid blend was MASKING this by concentrating volume on the
                # first two ranks. That is a blunt mask, not a fix, and it cost discrimination
                # everywhere. This is the mechanism it was standing in for.
                appear[i] = row.get('appearance_rate')
                if appear[i] is None:
                    appear[i] = 0.0 if beyond else 1.0
                crows[i].setdefault('allocation', {})[field] = {
                    'position_group_share_measured': gs[pos], 'depth_rank_in_group': rank,
                    'depth_share_in_group_measured': row.get('unconditional_expected_share'),
                    'appearance_rate_measured': appear[i],
                    'rank_beyond_measured_table': beyond,
                    'APPEARANCE_SEMANTICS': 'claim is share GIVEN he plays; this is P(he plays) '
                                            'at his depth rank, so the product is unconditional.',
                }
        # claims become unconditional before they are normalised against each other
        claims = [c * appear[i] for i, c in enumerate(claims)]
        sp, sd = sum(claims), sum(dvals)
        w = []
        for i in range(len(crows)):
            pn = (claims[i] / sp) if sp > 0 else 0.0
            dn = (dvals[i] / sd) if sd > 0 else 0.0
            if pn <= 0 and dn <= 0:
                w.append(0.0)
            elif pn <= 0 or dn <= 0:
                # one side has no evidence at all; take half the other rather than zero, so a
                # player is never silently removed from a club's offence by a missing measure
                w.append(max(pn, dn) * 0.5)
            else:
                b = DEPTH_CLAIM_BLEND if blend is None else blend
                w.append((pn ** b) * (dn ** (1.0 - b)))
        sw = sum(w)
        if not sw:
            acct[field] = {'state': 'NO_CLAIM_AND_NO_DEPTH_ANYWHERE',
                           'club_total': round(team_total, 4)}
            continue
        for i, r in enumerate(crows):
            r[field] = team_total * w[i] / sw
            a = r.setdefault('allocation', {}).setdefault(field, {})
            a.update({'claim_normalised': round((claims[i] / sp) if sp else 0.0, 5),
                      'prior_expected_share_normalised': round((dvals[i] / sd) if sd else 0.0, 5),
                      'final_share': round(w[i] / sw, 5)})
        acct[field] = {'club_total': round(team_total, 4), 'n_players': len(crows),
                       'claim_sum_before_normalising': round(sp, 4),
                       'IDENTITY_BY_CONSTRUCTION': True}
    return acct


def finalize(r):
    """Volume -> yardage and red-zone opportunity, once allocation has fixed the volume."""
    eff = r.get('efficiency') or {}
    tg = r.get('targets')
    cr = r.get('carries')
    pa = r.get('pass_attempts')

    def mul(a, b):
        return None if (a is None or b is None) else a * b

    r['receptions'] = mul(tg, eff.get('catch_rate'))
    r['rec_yards'] = mul(tg, eff.get('yards_per_target'))
    r['rush_yards'] = mul(cr, eff.get('yards_per_carry'))
    r['pass_yards'] = mul(pa, eff.get('yards_per_attempt'))
    inten = r.get('rz_intensity') or {}
    r['rec_rz_opps'] = mul(tg, inten.get('rec'))
    r['rush_rz_opps'] = mul(cr, inten.get('rush'))
    r['rec_far_opps'] = (None if tg is None else max(0.0, tg - (r['rec_rz_opps'] or 0.0)))
    r['rush_far_opps'] = (None if cr is None else max(0.0, cr - (r['rush_rz_opps'] or 0.0)))
    if r['position'] == 'QB':
        r['rec_rz_opps'] = None
        r['rec_far_opps'] = None
    # receptions can never exceed targets
    if r.get('receptions') is not None and tg is not None and r['receptions'] > tg:
        r['receptions_clamped_to_targets'] = True
        r['receptions'] = tg
    return r


def dk_points(row, td_row, bonus, ip):
    """DK classic points from projected volume. Returns points and the line items."""
    py = row.get('pass_yards') or 0.0
    ry = row.get('rush_yards') or 0.0
    cy = row.get('rec_yards') or 0.0
    rec = row.get('receptions') or 0.0
    pa = row.get('pass_attempts') or 0.0
    pass_td = (td_row or {}).get('pass_td') or 0.0
    rush_td = (td_row or {}).get('rush_td') or 0.0
    rec_td = (td_row or {}).get('rec_td') or 0.0
    items = {
        'pass_yards': py * DK['pass_yd'], 'pass_td': pass_td * DK['pass_td'],
        'interceptions': -(pa * (ip or 0.0)) * abs(DK['int']),
        'rush_yards': ry * DK['rush_yd'], 'rush_td': rush_td * DK['rush_td'],
        'receptions': rec * DK['rec'], 'rec_yards': cy * DK['rec_yd'],
        'rec_td': rec_td * DK['rec_td'],
    }
    bp_rec = bonus_p(bonus, 'rec', cy)
    bp_rush = bonus_p(bonus, 'rush', ry)
    bp_pass = bonus_p(bonus, 'pass', py)
    items['bonus_100_rec'] = (bp_rec or 0.0) * DK['bonus_100_rec']
    items['bonus_100_rush'] = (bp_rush or 0.0) * DK['bonus_100_rush']
    items['bonus_300_pass'] = (bp_pass or 0.0) * DK['bonus_300_pass']
    return round(sum(items.values()), 4), {k: round(v, 4) for k, v in items.items()}


def allocate_club_td(team_expected_td, pass_share, rows, rates):
    """Split a club's touchdown pool by TYPE and allocate each half. Mutates rows.

    BY TYPE, NOT BY POSITION. A running back's receiving touchdown is a passing touchdown and a
    receiver's end-around is a rushing one, so the halves are 'thrown' and 'run', and a player
    can draw from both. The quarterback's passing touchdowns ARE the passing half -- the same
    scores his receivers catch -- which is why they are not allocated a second time out of it.
    """
    if team_expected_td is None or pass_share is None:
        for r in rows:
            r['td'] = {'state': 'TEAM_POOL_UNKNOWN', 'NOT_ZERO': True}
        return {'state': 'NOT_ALLOCATED',
                'reason': 'TEAM_EXPECTED_TD_UNKNOWN' if team_expected_td is None
                          else 'PASS_SHARE_UNKNOWN'}
    pools = {'rec': team_expected_td * pass_share,
             'rush': team_expected_td * (1.0 - pass_share)}
    acct = {}
    for half, pool in pools.items():
        unscaled = {}
        for r in rows:
            rt = rates.get(r['position']) or {}
            brz = rt.get('td_per_rz_opportunity')
            bfar = rt.get('td_per_non_rz_opportunity')
            if brz is None:
                continue
            rz = r.get(f'{half}_rz_opps')
            far = r.get(f'{half}_far_opps')
            if rz is None and far is None:
                continue
            unscaled[id(r)] = brz * (rz or 0.0) + (bfar or 0.0) * (far or 0.0)
        tot = sum(unscaled.values())
        if not tot:
            acct[half] = {'state': 'NO_UNSCALED_MASS', 'pool': round(pool, 4)}
            continue
        k = pool / tot
        for r in rows:
            if id(r) in unscaled:
                r.setdefault('td', {})[f'{half}_td'] = round(unscaled[id(r)] * k, 5)
        acct[half] = {'state': 'SCALED', 'pool': round(pool, 4),
                      'unscaled_sum': round(tot, 4), 'scale': round(k, 4),
                      'SCALE_IS_A_DIAGNOSTIC': (
                          'a scale far from 1.0 means the measured rates and the club volume '
                          'disagree about how many touchdowns this offence produces. It is '
                          'reported so a units error cannot hide inside it -- an earlier run '
                          'summed two games of opportunity against a one-game pool and the '
                          'scale silently absorbed the factor of two.')}
    # the quarterback's passing touchdowns are the passing half, divided by who throws
    pa = {id(r): (r.get('pass_attempts') or 0.0) for r in rows if r['position'] == 'QB'}
    tot_pa = sum(pa.values())
    for r in rows:
        if r['position'] == 'QB' and tot_pa:
            r.setdefault('td', {})['pass_td'] = round(pools['rec'] * pa[id(r)] / tot_pa, 5)
    acct['qb_pass_td_pool'] = round(pools['rec'], 4)
    acct['PASS_TD_NOT_DOUBLE_COUNTED'] = (
        'the passing half is credited once to the receivers as receiving touchdowns and once to '
        'the quarterback as passing touchdowns, which is correct: DK pays the catcher six and '
        'the thrower four for the same score.')
    return acct


# --------------------------------------------------------------------------------- assembly
def build():
    from nfl.tools import dst_model, player_prior, td_rates
    for f, nm in ((POST, 'post-inactives state'), (ROLE, 'role state'), (RATES, 'td rates')):
        if not f.exists():
            return Outcome.blocked('V1_INPUT_ABSENT', f'{nm} missing at {f.name}',
                                   cause=Cause.DATA)
    post = json.loads(POST.read_text())
    role = json.loads(ROLE.read_text())['states']
    rates_art = json.loads(RATES.read_text())
    prates = rates_art['positional_rates']
    pto = rates_art['points_to_td']
    pass_share = (rates_art['pass_rush_split'] or {}).get('mean_pass_share_of_offensive_td')

    po = player_prior.load_panel()
    if po.state.name != 'PASS':
        return po
    panel = po.value
    pos_of = player_prior.position_index()
    name_ix = player_prior.name_index()
    ident, unresolved, suffixed = resolve_slate_identities(post, name_ix)
    bonus = bonus_rates(panel, pos_of)
    depth = depth_shares(panel, pos_of)
    ip = int_rate(panel, pos_of)['int_per_attempt']
    tv_all, implied, league_mean = team_volume(panel, post['environment'].get('games') or {})

    # opponent implied total, for the defence/special-teams points-allowed term
    opponent_implied = {}
    for game, e in (post['environment'].get('games') or {}).items():
        if '@' not in game:
            continue
        away, home = game.split('@')
        opponent_implied[away] = e.get('home_implied')
        opponent_implied[home] = e.get('away_implied')
    dst_built = dst_model.build()
    if isinstance(dst_built, tuple):
        _dst_art, dst_spread, dst_rates = dst_built
    else:
        _dst_art, dst_spread, dst_rates = None, {'state': 'NOT_ESTIMATED'}, {}

    # OPEN IDENTITY CONFLICTS ARE NOT PROJECTED. A declared rule, applied here rather than
    # detected afterwards: projecting a name whose football identity is unsettled assigns
    # opportunity to somebody we have not established exists. IDC-02 is the live case -- the
    # research named 'Matthew McClain' as a predicted New York starter and the DK universe
    # carries 'Malik McClain'. The first V1 run gave him 0.85 points, which is small and still
    # wrong: the rule is categorical, not proportional to the number.
    conflicted = set()
    for c in (post.get('identity_conflicts') or ()):
        if not str(c.get('status', '')).startswith('OPEN'):
            continue
        blob = f"{c.get('subject', '')} {c.get('claim', '')} {c.get('resolution', '')}"
        for dk_id, pl in post['players'].items():
            surname = (pl.get('name') or '').split()[-1]
            if surname and surname in blob:
                conflicted.add(dk_id)

    rows, by_club = {}, collections.defaultdict(list)
    skipped = collections.Counter()
    for dk_id, p in post['players'].items():
        pos, club, nm = p.get('position'), p.get('team'), p.get('name')
        rs = role.get(dk_id) or {}
        state, band = rs.get('state'), rs.get('role_band')
        base = {'dk_id': dk_id, 'name': nm, 'position': pos, 'team': club,
                'salary': p.get('salary'), 'role_state': state, 'role_band': band,
                'askable_ceiling': rs.get('askable_ceiling'), 'capped': rs.get('capped'),
                'is_predicted_starter': bool(rs.get('in_predicted_group')),
                'availability': rs.get('availability')}
        if dk_id in conflicted:
            base.update({'projection_state': 'WITHHELD_IDENTITY_CONFLICT_OPEN',
                         'dk_points': None,
                         'NOT_ZERO': 'an open identity conflict is withheld, not projected at '
                                     'zero. Zero would be a forecast about a player we have '
                                     'not established.'})
            rows[dk_id] = base
            skipped['IDENTITY_CONFLICT_OPEN'] += 1
            continue
        if state == 'NOT_PLAYING':
            base.update({'projection_state': 'NOT_PLAYING_REPORTED_INACTIVE',
                         'dk_points': None,
                         'NOT_ZERO': 'reported inactive; he is not projected at zero, he is '
                                     'not projected. A zero would read as a forecast.'})
            rows[dk_id] = base
            skipped['NOT_PLAYING'] += 1
            continue
        if pos == 'DST' or state == 'TEAM_UNIT':
            opp_imp = opponent_implied.get(club)
            d = dst_model.project(club, opp_imp, dst_rates, dst_spread)
            base.update({'projection_state': ('PROJECTED_DST' if d.get('dk_points') is not None
                                              else f"DST_{d['state']}"),
                         'dk_points': d.get('dk_points'), 'dst': d,
                         'opponent_implied_total': opp_imp})
            rows[dk_id] = base
            skipped['DST' if d.get('dk_points') is None else 'DST_PROJECTED'] += 1
            continue
        if pos not in SKILL:
            base.update({'projection_state': f'POSITION_PATHWAY_UNDEFINED_{pos}',
                         'dk_points': None})
            rows[dk_id] = base
            skipped[f'POS_{pos}'] += 1
            continue
        tv = tv_all.get(club) or {}
        if tv.get('state') != 'OK':
            base.update({'projection_state': 'CLUB_VOLUME_UNKNOWN', 'dk_points': None,
                         'detail': tv.get('state')})
            rows[dk_id] = base
            skipped['NO_CLUB_VOLUME'] += 1
            continue
        idr = ident.get(dk_id)
        gsis = (idr or {}).get('gsis_id')
        if not gsis:
            base.update({'projection_state': 'COLD_START_IDENTITY_UNRESOLVED',
                         'IDENTITY_NOT_GUESSED': (
                             'not present in the roster capture. The prior is queried at the '
                             'broad positional tier for his band rather than an identifier '
                             'being invented -- a guessed identifier once scored a '
                             'quarterback as a receiver.')})
        prior = (player_prior.hierarchical(panel, gsis, pos, band, FORECAST_SEASON,
                                           THROUGH_SEASON, club=club) if gsis else
                 player_prior.cohort_estimate(panel, pos, band, FORECAST_SEASON,
                                              THROUGH_SEASON))
        cur, cur_n = (current_season_shares(panel, gsis, club, pos) if gsis else ({}, 0))
        pr = project_player(panel, gsis, pos, band, club, tv, prates, cur, cur_n, prior,
                            is_predicted_starter=bool(rs.get('in_predicted_group')),
                            depth=depth)
        base.update(pr)
        base['projection_state'] = ('PROJECTED' if gsis else 'PROJECTED_COLD_START')
        base['gsis_id'] = gsis
        rows[dk_id] = base
        by_club[club].append(base)

    # opportunity allocation, per club, satisfying every club identity by construction
    groups = group_shares(panel, pos_of)
    alloc_acct = {}
    for club, crows in by_club.items():
        alloc_acct[club] = allocate_opportunity(crows, tv_all.get(club) or {}, depth, groups)
        for r in crows:
            finalize(r)

    # club touchdown pools
    td_acct = {}
    for club, crows in by_club.items():
        imp = implied.get(club)
        team_td = td_rates.expected_team_td(imp, pto)
        td_acct[club] = allocate_club_td(team_td, pass_share, crows, prates)
        td_acct[club]['implied_total'] = imp
        td_acct[club]['team_expected_td'] = (round(team_td, 4) if team_td is not None else None)
        td_acct[club]['V0_WOULD_HAVE_SAID'] = (round(imp / 7.0, 4) if imp else None)

    for r in rows.values():
        # 'PROJECTED_DST' also starts with 'PROJECTED', and this loop scored it with the skill
        # scorer -- no yards, no touchdowns -- overwriting every defence with 0.00. An explicit
        # membership test, not a prefix.
        if r.get('projection_state') in ('PROJECTED', 'PROJECTED_COLD_START'):
            pts, items = dk_points(r, r.get('td'), bonus, ip)
            r['dk_points'] = pts
            r['dk_line_items'] = items
    for r in rows.values():
        r.pop('_claims', None)
    return {'post': post, 'rows': rows, 'team_volume': tv_all, 'td_account': td_acct,
            'allocation_account': alloc_acct, 'group_shares': groups,
            'DEPTH_CLAIM_BLEND': DEPTH_CLAIM_BLEND,
            'identity': {'resolved': len(ident), 'unresolved': unresolved,
                         'suffix_normalised': suffixed,
                         'position_disagreements': [
                             {'name': post['players'][k]['name'],
                              'dk_position': post['players'][k]['position'],
                              'roster_position': v['roster_position']}
                             for k, v in ident.items() if not v['position_agrees']]},
            'bonus_rates': bonus, 'int_rate': ip, 'skipped': dict(skipped),
            'depth_shares': depth,
            'rates_artifact': {'points_to_td': pto, 'pass_share': pass_share},
            'implied': implied, 'league_mean_implied': league_mean,
            'opponent_implied': opponent_implied,
            'dst_residual_spread': {k: v for k, v in (dst_spread or {}).items()
                                    if k != 'residuals'}}


# ------------------------------------------------------- appearance probability, measured
def depth_shares(panel, pos_of, through=None):
    """Share of club volume by depth rank, and how often each rank appears at all. MEASURED.

    THIS IS THE FIX FOR A BACKUP INHERITING A STARTER'S WORKLOAD, and it is a decomposition
    rather than a discount:

        expected share  =  P(he appears)  x  E[share | he appears]

    A second quarterback's starter history is real -- he did take those snaps, for another club
    in another season -- so shrinking his efficiency or his role band is the wrong instrument.
    What is small is the PROBABILITY he takes them this Sunday. Measured over 2,305 club-weeks
    the first quarterback takes 98.0 per cent of pass attempts with a median of 100, and a
    second appears in 325 of those weeks taking 14.1 per cent when he does, so his
    unconditional expectation is about two per cent.

    Quarterback is the one position where the role is genuinely exclusive, so only it is
    adjusted this way. Backs and receivers really do share volume week to week, and their
    competition is settled by reconciliation against club totals instead.
    """
    FIELD = {'QB': 'pass_attempts', 'RB': 'carries', 'WR': 'targets', 'TE': 'targets'}
    out = {}
    for pos, fld in FIELD.items():
        cw = collections.defaultdict(list)
        for g, seasons in panel['players'].items():
            if pos_of.get(g) != pos:
                continue
            for s, weeks in seasons.items():
                if int(s) > (THROUGH_SEASON if through is None else through):
                    continue
                for w, d in weeks.items():
                    club = d.get('team')
                    if club:
                        cw[(club, s, w)].append(d.get(fld) or 0)
        ranks = collections.defaultdict(list)
        n_club_weeks = 0
        for lst in cw.values():
            tot = sum(lst)
            if tot < 15:
                continue
            n_club_weeks += 1
            for i, a in enumerate(sorted(lst, reverse=True)):
                ranks[i + 1].append(a / tot)
        rows = {}
        for r in sorted(ranks):
            v = ranks[r]
            n = len(v)
            appear = n / n_club_weeks if n_club_weeks else None
            cond = sum(v) / n
            rows[f'rank_{r}'] = {
                'n_club_weeks_present': n, 'appearance_rate': round(appear, 5),
                'conditional_mean_share': round(cond, 5),
                'unconditional_expected_share': round(appear * cond, 5),
                'median_conditional': round(sorted(v)[n // 2], 5),
            }
        out[pos] = {'state': 'MEASURED', 'volume_field': fld,
                    'n_club_weeks': n_club_weeks, 'by_rank': rows}
    out['APPLIED_TO'] = ['QB']
    out['WHY_ONLY_QB'] = (
        'the role is exclusive -- one man throws. Backs and receivers share volume genuinely, '
        'so theirs is settled by reconciliation against club totals rather than by an '
        'appearance probability.')
    return out


# ------------------------------------------------------------------------- identities, output
RECONCILE_TOLERANCE = 0.02


def check_identities(rows, tv):
    """Every club identity, checked rather than assumed. Allocation makes these hold by
    construction, so a failure here means the construction is broken, not that a tolerance is
    tight."""
    out, failures = [], 0
    LADDER = (('targets', 'proj_targets', 'targets sum to club targets'),
              ('carries', 'proj_rush_attempts', 'carries sum to club rush attempts'),
              ('pass_attempts', 'proj_pass_attempts', 'attempts sum to club pass attempts'))
    for club, vol in sorted(tv.items()):
        if vol.get('state') != 'OK':
            continue
        crows = [x for x in rows.values() if x.get('team') == club
                 and x.get('targets') is not None]
        if not crows:
            continue
        for fld, teamfld, desc in LADDER:
            t = vol.get(teamfld)
            if not t:
                out.append({'club': club, 'identity': fld, 'state': 'CLUB_TOTAL_UNKNOWN'})
                continue
            s = sum((x.get(fld) or 0.0) for x in crows)
            ratio = s / t
            ok = abs(ratio - 1.0) <= RECONCILE_TOLERANCE
            failures += (0 if ok else 1)
            out.append({'club': club, 'identity': fld, 'description': desc,
                        'player_sum': round(s, 4), 'club_total': round(t, 4),
                        'ratio': round(ratio, 5), 'state': 'OK' if ok else 'VIOLATED'})
        # receptions never exceed targets, per player
        for x in crows:
            if (x.get('receptions') or 0) > (x.get('targets') or 0) + 1e-9:
                failures += 1
                out.append({'club': club, 'identity': 'receptions_le_targets',
                            'player': x['name'], 'state': 'VIOLATED'})
    # club touchdowns sum to the club pool
    return out, failures


def summarise(art):
    rows = art['rows']
    proj = [x for x in rows.values() if x.get('dk_points') is not None]
    lvl = sorted((x['dk_points'] for x in proj), reverse=True)
    n = len(lvl) or 1
    return {
        'n_universe': len(rows), 'n_projected': len(proj),
        'n_unavailable': len(rows) - len(proj),
        'mean_dk_points': round(sum(lvl) / n, 4),
        'top_1': round(lvl[0], 3) if lvl else None,
        'top_10_mean': round(sum(lvl[:10]) / min(10, n), 3),
        'top_100_mean': round(sum(lvl[:100]) / min(100, n), 3),
        'median': round(lvl[n // 2], 3) if lvl else None,
        'n_exactly_zero': sum(1 for x in proj if x['dk_points'] == 0.0),
        'states': dict(collections.Counter(x.get('projection_state') for x in rows.values())),
        'by_position': {p: {'n': sum(1 for x in proj if x['position'] == p),
                            'mean': round(sum(x['dk_points'] for x in proj
                                              if x['position'] == p)
                                          / max(1, sum(1 for x in proj
                                                       if x['position'] == p)), 3)}
                        for p in SKILL},
    }


def main() -> int:
    art = build()
    if not isinstance(art, dict):
        print(art.render() if hasattr(art, 'render') else art)
        return 1
    ident, fails = check_identities(art['rows'], art['team_volume'])
    art['identities'] = ident
    art['identity_failures'] = fails
    art['summary'] = summarise(art)
    art['spec_version'] = SPEC_VERSION
    art['label'] = LABEL
    art['CONSTANTS_PROVENANCE'] = {k: (v[0] if not isinstance(v[0], dict) else v[0], v[1])
                                   for k, v in CONSTANTS_PROVENANCE.items()}
    art['HOLDOUT'] = (f'every prior and every rate is fitted at or before {THROUGH_SEASON}. '
                      f'The {FORECAST_SEASON} weeks enter only as current-season evidence with '
                      f'declared weight, never as training data, so forward-chained evaluation '
                      f'on unseen {FORECAST_SEASON} weeks remains honest.')
    art.pop('post', None)
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True, default=str))

    s = art['summary']
    o = (Outcome.fail('V1_IDENTITIES_VIOLATED', f'{fails} club identities outside tolerance',
                      failures=fails)
         if fails else
         Outcome.ok('V1_PROJECTED', s, f"{s['n_projected']} of {s['n_universe']} projected",
                    identities_checked=len(ident)))
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    print(f"  universe {s['n_universe']}  projected {s['n_projected']}  "
          f"unavailable {s['n_unavailable']}  exact zeros {s['n_exactly_zero']}")
    print(f"  identities {len(ident)} checked, {fails} violated")
    print(f"  top1 {s['top_1']}  top10 {s['top_10_mean']}  top100 {s['top_100_mean']}  "
          f"median {s['median']}  mean {s['mean_dk_points']}")
    for p, v in s['by_position'].items():
        print(f"    {p:3s} n={v['n']:3d} mean {v['mean']}")
    for k, v in s['states'].items():
        print(f"    {k}: {v}")
    print(f"  -> {OUT.relative_to(_REPO)}")
    return 0 if not fails else 1


if __name__ == '__main__':
    raise SystemExit(main())
