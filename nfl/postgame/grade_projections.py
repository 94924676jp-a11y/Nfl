"""Phase 2 and Phase 10: the frozen board against what happened, stat by stat.

NOT ONE MAE. The request is explicit and it is right: a single error number
says the model was wrong and nothing about WHERE. Every supported stat is
graded on its own, and every actual is placed in the predicted distribution as
well as differenced against the mean, because a projection that is 8 yards low
on a mean but inside p25-p75 is a different object from one that is 8 yards low
and outside p90.

WHAT ONE GAME CAN AND CANNOT DO. It can show a defect and generate a
hypothesis. It cannot estimate calibration: with roughly thirty players and
twelve stats the bucket counts are small, correlated within player, and
correlated within game. The nominal shares are carried so the LEDGER
accumulates toward them across slates -- not so tonight can be scored against
them.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.postgame import join_provenance as JP                        # noqa: E402
from nfl.postgame import outcome as OC                                 # noqa: E402
from nfl.dfs.scoring import statline as SL                             # noqa: E402
import pathlib as _pl

from nfl.dfs import player_universe as PU
from nfl.dfs.scoring import draftkings as DK                           # noqa: E402
from nfl.dfs.scoring import fanduel as FD                              # noqa: E402
from nfl.dfs.showdown import universe as UNI                           # noqa: E402

SPEC_VERSION = 'nfl-postgame-grade-projections-1'
PCT = (10, 25, 50, 75, 90, 95)

#: model stat -> outcome key. Explicit, because an implicit mapping is how a
#: passing stat gets graded against a rushing column.
MAP = {
    'pass_att': ('qb', 'att'), 'pass_cmp': ('qb', 'cmp'),
    'pass_yards': ('qb', 'pyds'), 'pass_td': ('qb', 'ptd'),
    'interceptions': ('qb', 'int'),
    'rush_att': ('rushing', 'carries'),
    'rush_yards': ('rushing_total', 'rushing_yards'),
    'rush_td': ('rushing', 'rushing_td'),
    'targets': ('receiving', 'targets'),
    'receptions': ('receiving', 'receptions'),
    'rec_yards': ('receiving', 'receiving_yards'),
    'rec_td': ('receiving', 'receiving_td'),
}


def _q(v):
    return {f'p{k}': float(np.percentile(v, k)) for k in PCT}


def grade(outcome_path=None, sl=None) -> Outcome:
    """Grade one slate. `sl` selects WHICH slate; the default is unchanged.

    This read OC.PREGAME_FROZEN and called OC.assert_pregame_untouched() with
    no argument, so the frozen board it graded was always DET_BUF_2026W2 --
    whatever outcome_path it was handed. A grader that accepts one game's
    RESULT while reading another game's BOARD does not fail; it reports a
    catastrophically bad model. Passing the slate through makes the pair move
    together, which is the whole reason Slate is one object.
    """
    # THE SLATE IS NEVER GUESSED FROM THE OUTCOME PATH.
    #
    # A first version derived it as outcome_path.parent.parent, which looks
    # reasonable and is wrong: callers pass a bare fixture outcome with no
    # slate around it, so the derived root had no frozen/ directory and the
    # guard failed PREGAME_FROZEN_SET_MUTATED with all three files "missing".
    # It also silently re-pointed the frozen board for anyone who passed only
    # an outcome path.
    #
    # `sl` defaults to the default slate -- exactly the old behaviour -- and a
    # caller wanting another slate passes it. Same refusal-to-guess as
    # outcome.slate(): inferring a directory from a filename is how a grader
    # reads the wrong game.
    sl = sl or OC._DEFAULT
    got = OC.require(outcome_path, sl=sl)
    if got.state is not State.PASS:
        return got
    result = got.value
    intact = OC.assert_pregame_untouched(sl)
    if intact.state is not State.PASS:
        return intact
    F = sl.pregame_frozen
    z = np.load(F / 'sealed_player_draws.npz')
    man = json.loads((F / 'sealed_player_draws_manifest.json').read_text())
    names = json.loads((F.parent / 'frozen_board_names.json').read_text())
    L = man['layers']
    # THE UNIVERSE IS THE UNION OF EVERY DK-BEARING LAYER, DISCOVERED.
    #
    # This read `L['dk_scoring']['row_ids']`, which is 30 of the 32 players in
    # the sealed ATL@GB artifact. The missing two are the kickers, whose DK
    # points live in the `kicking` layer -- so no kicker was ever enumerated
    # here, and therefore no kicker has ever been graded. That is worse than
    # the DFS omission it came from: a class of players that never gets graded
    # makes the prospective ledger look more complete than it is, and the
    # learning loop never learns it is blind.
    dk_draws, dk_report = PU.dk_points_by_id(
        man, z, consumer='nfl.postgame.grade_projections')
    ids = sorted(dk_draws)
    kicker_ids = {g for g, layer in
                  PU.dk_universe(man, consumer='nfl.postgame.grade_projections'
                                 )['layer_by_id'].items()
                  if layer == 'kicking'}
    n = int(next(iter(dk_draws.values())).shape[0]) if dk_draws else 0
    # Identity by normalised name: DraftKings and the stat feed spell the
    # same man differently ('James Cook III' / 'James Cook').
    actual = {UNI.norm(k): v for k, v in result['players'].items()}
    # AND BY IDENTITY, WHICH IS THE ONLY THING THAT WORKS FOR A KICKER.
    #
    # The name index above needs `frozen_board_names.json` to know the player.
    # It does not know either kicker -- their gsis_ids are absent from it -- so
    # `nm` fell back to the raw gsis_id, matched nothing, and the kicker was
    # graded against a ZERO line while the outcome sat right there holding
    # 'Jake Bates' with 4 extra points and a field goal from the 30s.
    #
    # The outcome's own rows carry `player_id`, so identity is available and
    # exact. Third instance of the same lesson today: prefer the id, fall back
    # to the name.
    actual_by_id = {}
    for _nm, _v in result['players'].items():
        _pid = (_v or {}).get('player_id')
        if _pid:
            actual_by_id.setdefault(_pid, dict(_v, _outcome_name=_nm))
    # Team per board player, so an absent one can be told apart from an
    # uncovered one. A board player with no outcome row whose CLUB is in the
    # outcome recorded nothing, and zero is his measurement -- dropping him
    # would grade the model only on the players it got onto the field.
    uni = UNI.build()
    # From `players`, not `playable`: the officially-inactive rows are
    # excluded from the DFS pool and still belong in the GRADE. Skyler Bell
    # was hard-zeroed before kickoff and the board projected him anyway; the
    # model's number for him is exactly the kind that must not vanish.
    teams = ({UNI.norm(p['name']): p['team'] for p in uni.value['players']}
             if uni.state is State.PASS else {})
    # THE CLUB OF A PLAYER IN A SEALED RUN IS A PROPERTY OF THE SEALED RUN.
    #
    # `teams` above comes from the DFS universe, which is built from the DK
    # SALARY file -- so a player absent from that file has no club here. That
    # was invisible while grading enumerated only dk_scoring; the moment
    # kickers were included they came back CLUB_NOT_COVERED_BY_THE_OUTCOME,
    # which reads as "the outcome does not cover his team" and was actually
    # "the salary file does not list him".
    #
    # The manifest already answers it, by gsis_id, for every layer: run_forecast
    # records row_teams when it writes each one. Resolving by IDENTITY from the
    # artifact is both correct and better than a normalised-name lookup into a
    # different source.
    # row_teams appears in BOTH shapes across layers: a dict keyed by gsis_id,
    # and a list positionally aligned to row_ids. Assuming either one crashes on
    # the other, so both are read and a mismatched list length is skipped rather
    # than zipped short -- a truncated zip would attach one player's club to
    # another, which is worse than having no club at all.
    team_by_gid = {}
    for _spec in (man.get('layers') or {}).values():
        _rt = (_spec or {}).get('row_teams')
        if isinstance(_rt, dict):
            pairs = _rt.items()
        elif isinstance(_rt, (list, tuple)):
            _ids = (_spec or {}).get('row_ids') or []
            pairs = zip(_ids, _rt) if len(_ids) == len(_rt) else ()
        else:
            pairs = ()
        for _g, _tm in pairs:
            if _tm:
                team_by_gid.setdefault(_g, _tm)
    rows, not_in_outcome, zeroed = [], [], []
    for gid in ids:
        # EVERY ROW STATES HOW ITS NUMBER ARRIVED. See join_provenance.py.
        # A zero reached by a failed lookup and a zero the man actually scored
        # are the same float and opposite facts, and only this block still
        # knows which one it is -- a later audit cannot recover it.
        named = gid in names
        nm = names.get(gid, gid)
        a, prov = actual_by_id.get(gid), None
        if a is not None:
            prov = JP.stamp(JP.MATCHED_BY_IDENTITY, key=gid,
                            zero_basis=JP.REAL_ZERO)
        elif named and actual.get(UNI.norm(nm)) is not None:
            # Name fallback, legitimate only because the outcome row carried
            # no player_id. Never used while an id is available.
            a = actual[UNI.norm(nm)]
            prov = JP.stamp(JP.MATCHED_BY_NAME, key=UNI.norm(nm),
                            zero_basis=JP.REAL_ZERO)
        if a is None:
            # WHAT DECIDES A GOVERNED ZERO IS THE CLUB, NOT THE NAME, and the
            # club is resolved BY IDENTITY from the sealed manifest.
            #
            # My first cut here refused any id the name index could not name,
            # calling it IDENTITY_NOT_ESTABLISHED. That was wrong and the
            # postgame harness caught it: the two ids with no display name in
            # `frozen_board_names.json` are the KICKERS, and a gsis_id IS an
            # identity -- the missing piece is a label for a report, not the
            # ability to ask the outcome about him. Refusing them would have
            # re-broken kicker grading from the opposite direction.
            #
            # `resolve_absent` ignores the name entirely (it decides on the
            # club against the outcome's club set), so an unnamed id is safe
            # to pass through it. Measured on this slate: all 7 absent players
            # get their club from `team_by_gid` by identity, and the
            # name-derived club agrees in all 7 -- the name path adds no
            # coverage here and is kept only for a board row the manifest
            # happens not to carry.
            club = team_by_gid.get(gid) or (teams.get(UNI.norm(nm))
                                           if named else None)
            if club is None:
                # NO CLUB AT ALL, so we cannot say WHOSE absence this is.
                # Not "he recorded nothing" and not "his game is unpublished"
                # -- we hold an id string that nothing in the sealed run
                # recognises as a player on either roster. That is the state
                # a zero used to be invented for.
                not_in_outcome.append(
                    {'player': nm, 'reason': JP.IDENTITY_NOT_ESTABLISHED,
                     'join': JP.IDENTITY_NOT_ESTABLISHED,
                     'detail': 'no club by identity or by name, so his '
                               'absence cannot be governed either way'})
                continue
            line, code = OC.resolve_absent(nm, club, result)
            if line is None:
                not_in_outcome.append({'player': nm, 'reason': code,
                                       'join': JP.PLAYER_NOT_IN_OUTCOME})
                continue
            a = {'team': club, 'position': None, **line}
            zeroed.append(nm)
            # Every zero on this row rests on the absence rule, not on play.
            prov = JP.stamp(JP.ABSENCE_RESOLVED_TO_ZERO, key=code,
                            zero_basis=JP.ABSENCE_RESOLVED_TO_ZERO)
        sl = SL.assemble(gid, nm, L, z, n)
        per_stat = {}
        for stat, (layer, metric) in MAP.items():
            spec = L.get(layer)
            k = f'{layer}__{metric}'
            if not spec or gid not in (spec.get('row_ids') or []) \
                    or k not in z.files:
                per_stat[stat] = {'state': 'NOT_MODELLED'}
                continue
            v = np.asarray(z[k])[spec['row_ids'].index(gid)].astype(float)
            act = a.get(stat)
            q = _q(v)
            per_stat[stat] = {
                'state': 'GRADED' if act is not None else 'NOT_IN_OUTCOME',
                'actual': act, 'mean': float(v.mean()),
                'median': float(np.median(v)), **q,
                'abs_error': (abs(act - float(v.mean()))
                              if act is not None else None),
                'signed_error': (float(v.mean()) - act
                                 if act is not None else None),
                'percentile_of_actual': (float((v < act).mean())
                                         if act is not None else None),
                'bucket': OC.percentile_bucket(act, q),
            }
        # SCORING, both sites, from the same actual stat line.
        act_sl = SL.from_line(
            1, pass_yards=a.get('pass_yards') or 0, pass_td=a.get('pass_td') or 0,
            interceptions=a.get('interceptions') or 0,
            rush_yards=a.get('rush_yards') or 0, rush_td=a.get('rush_td') or 0,
            rec_yards=a.get('rec_yards') or 0,
            receptions=a.get('receptions') or 0, rec_td=a.get('rec_td') or 0)
        for site, fn, key in (('DRAFTKINGS', DK.score, 'dk'),
                              ('FANDUEL', FD.score, 'fd')):
            pred = (dk_draws[gid] if key == 'dk'
                    else DK.score(sl) - 0.5 * sl.receptions)
            if gid in kicker_ids:
                # A KICKER IS SCORED BY THE KICKER RULES, EXACTLY.
                #
                # I previously marked this KICKER_ACTUALS_INSUFFICIENT and
                # filed DEF-061 saying the outcome feed could not support it.
                # THAT WAS WRONG, and the error is worth recording: I read
                # `actuals.NUMERIC` -- a DIFFERENT loader, for the weekly stats
                # CSV -- and concluded the outcome lacked xp_made and the
                # field-goal distance buckets. This grader does not read that
                # file. It reads OUTCOME.json, where every player carries a
                # `kicking` sub-dict with fg_made, fg_att, xp_made, xp_att AND
                # fg_made_by_bucket. grade_portfolios.py has been reading it
                # all along, three lines that I had already looked at.
                #
                # So the actual is exact: Jake Bates 1 FG from the 30s and 4
                # extra points, Tyler Bass 5 of 6. Both sites' kicker rules are
                # identical here, so `fn` is used unchanged.
                k = a.get('kicking') or {}
                kick_sl = SL.from_line(
                    1,
                    fg_made=k.get('fg_made') or 0, fg_att=k.get('fg_att') or 0,
                    xp_made=k.get('xp_made') or 0, xp_att=k.get('xp_att') or 0,
                    fg_made_by_bucket=k.get('fg_made_by_bucket') or {})
                scorer = (DK.score_kicker if key == 'dk' else FD.score_kicker)
                act_pts = float(scorer(kick_sl)[0])
                q = _q(pred)
                per_stat[f'{key}_points'] = {
                    'state': 'GRADED', 'actual': act_pts,
                    'mean': float(pred.mean()),
                    'median': float(np.median(pred)), **q,
                    'abs_error': abs(act_pts - float(pred.mean())),
                    'signed_error': float(pred.mean()) - act_pts,
                    'percentile_of_actual': float((pred < act_pts).mean()),
                    'bucket': OC.percentile_bucket(act_pts, q),
                    'site': site, 'scored_by': 'kicker_rules',
                }
                continue
            act_pts = float(fn(act_sl)[0])
            q = _q(pred)
            per_stat[f'{key}_points'] = {
                'state': 'GRADED', 'actual': act_pts,
                'mean': float(pred.mean()), 'median': float(np.median(pred)),
                **q, 'abs_error': abs(act_pts - float(pred.mean())),
                'signed_error': float(pred.mean()) - act_pts,
                'percentile_of_actual': float((pred < act_pts).mean()),
                'bucket': OC.percentile_bucket(act_pts, q), 'site': site}
        row = {'player': nm, 'team': a.get('team'),
               'position': a.get('position'), 'stats': per_stat,
               'join_provenance': prov}
        # Refuse at the point of emission, not in a later sweep. A row that
        # leaves here unproven is indistinguishable from a correct one.
        for _stat, _d in per_stat.items():
            if _d.get('state') == 'GRADED':
                JP.assert_graded_row(row, actual=_d.get('actual'),
                                     where=f'{nm}/{_stat}')
        rows.append(row)
    # AGGREGATE BUCKETS, per stat and overall. Descriptive only.
    buckets = {}
    for r in rows:
        for stat, d in r['stats'].items():
            if d.get('state') != 'GRADED':
                continue
            b = buckets.setdefault(stat, {k: 0 for k in OC.BUCKETS})
            b[d['bucket']] = b.get(d['bucket'], 0) + 1
    overall = {k: sum(v.get(k, 0) for v in buckets.values())
               for k in OC.BUCKETS}
    total = sum(overall.values()) or 1
    return Outcome.ok(
        'PROJECTIONS_GRADED',
        value={'rows': rows, 'buckets_by_stat': buckets,
               'buckets_overall': overall,
               'overall_share': {k: overall[k] / total for k in OC.BUCKETS}},
        detail=f'{len(rows)} player(s) graded ({len(zeroed)} of them with no '
               f'recorded production), {len(not_in_outcome)} unscorable; '
               f'{total} stat-observation(s)',
        spec_version=SPEC_VERSION, n_players=len(rows),
        players_not_in_outcome=not_in_outcome,
        players_zero_by_absence=sorted(zeroed),
        zero_by_absence_is_a_measurement=(
            'his club is in the outcome, so the game was published and he '
            'recorded no carry, target or catch. Dropping him instead would '
            'be survivorship: it grades the model only on the players it got '
            'onto the field, and those are exactly the ones it got right.'),
        join_provenance=JP.audit_rows(rows),
        n_observations=total, nominal_shares=OC.NOMINAL,
        one_game_cannot_estimate_calibration=(
            'roughly thirty players and twelve stats give small bucket counts '
            'that are correlated within player and within game. These shares '
            'are descriptive. The ledger accumulates toward the nominal '
            'column across slates; tonight is not scored against it.'),
        is_measurement_not_development=True)


def main() -> int:
    o = grade()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    out = OC.DIR / 'GRADE_PROJECTIONS.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         **o.value}, indent=1, sort_keys=True))
    c = AC.claim(out, schema=['rows', 'buckets_overall'], label=out.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
