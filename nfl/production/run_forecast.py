"""The canonical production entrypoint.

    python3.12 -m nfl.production.run_forecast \
        --season 2026 --week 1 --game-id 2026_01_NE_SEA \
        --arm A --written-at 2026-09-09T22:00:00Z --out-dir /path

FAILS CLOSED. Every stage that cannot be executed correctly returns a named
refusal, and the run reports REFUSED rather than emitting a forecast.

`--written-at` is REQUIRED. The wall clock may stamp operational fields; it may
never stand in for a scientific clock, and there is no default that would let
it.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from nfl.production import authorization as AUTH                      # noqa: E402
from nfl.production import pipeline as PL                             # noqa: E402
from nfl.production import refusal as RF                              # noqa: E402
from nfl.prospective import artifact as ART                           # noqa: E402
from nfl.capture import registry as REG                               # noqa: E402
from nfl.production import qb_accounting as QBACC
from nfl.production import team_volume_v1 as TV
from nfl.production import qb_v1 as QBV1                             # noqa: E402
from nfl.production import derived as DERIVED                       # noqa: E402
from nfl.production import candidate_mode as CAND                   # noqa: E402
from nfl.production import kicking as KICK                          # noqa: E402
from nfl.production.nonqb import gadget_rush as GADGET              # noqa: E402
from nfl.product import names as NAMES                              # noqa: E402
from nfl.product import dk_scoring as DKS                           # noqa: E402
from nfl.production import draws_artifact as DA                     # noqa: E402
from nfl.identity import code_identity as CI                       # noqa: E402
from nfl.production import draw_coherence as DC                     # noqa: E402

# THE ONE BOUND ON EVERY PLAYER-SCOPED EXCLUSION, declared once.
#
# Two stages exclude a player they cannot place rather than refusing the game
# around him -- `identity_resolution` for a missing gsis_id, and the non-QB
# frame check for a missing gsis_id, position or team. Both are bounded by
# this: above it the roster feed is BROKEN rather than incomplete and the run
# refuses. It lived inside `_identity` as a local, so the second stage could
# not read it and refused the whole game around one player instead.
EXCLUSION_LIMIT = 0.01

ARMS = ('A', 'B', 'C')

#: The seal contract for a REFUSED C3. Written on every C3 run, whether or not
#: the refusal occurred, so that its ABSENCE means "sealed by an engine that
#: did not transport this" rather than "nothing went wrong". A key that appears
#: only on failure cannot distinguish a healthy run from an old one.
C3_REFUSAL_CONTRACT = 'c3-refusal-transport-1'

# WHAT A QUARTERBACK NUMBER ON THIS BOARD IS STILL WRONG ABOUT, IN ONE STRING.
#
# Recorded on every run that filters the QB pool, because the two limitations
# below survive that filter and a reader who sees an eligibility repair applied
# would otherwise reasonably infer the room is now sound. It is not. The string
# is general; the per-run evidence that instantiates it travels beside it in
# `qb3_configuration` and `qb_pool_eligibility`, so nothing here is asserted
# that the artifact does not also show.
QB_PARTICIPATION_LIMITATION = (
    'QB participation is QB3 (contract nfl/research/qb3/predeclaration_qb3.md, '
    'sha256 be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e). '
    'Filtering the QB pool on roster status removes ineligible quarterbacks '
    'and does NOT repair either known participation defect. (1) '
    'QB3_WEEK1_SEASON_BOUNDARY: in a season opener the incumbent signal is the '
    'PRIOR SEASON FINAL-GAME primary passer, the game a club is most likely to '
    'rest a starter in. Measured league-wide, the depth-chart QB1 equals that '
    'passer in only 59 of 160 week-1 rooms (0.3688), and 77 of 192 '
    'team-seasons (0.4010) end with a primary who is not that season modal '
    'starter (nfl/research/qb3/QB3_WEEK1_INCUMBENT_AUDIT.json). Removing an '
    'ineligible incumbent does not restore the bit; it moves the room from '
    'DISAGREE to NO_PREV_PRIMARY_IN_ROOM, whose cell (1,0) carries '
    'p_primary 0.4922 and P(share=0) 0.4735 against cell (1,1) 0.9046 and '
    '0.0736. (2) An unranked rostered quarterback is modelled at depth rank 3 '
    '(nfl/production/nonqb/qb_allocation.py, "r = 3"), which is a populated '
    'cell and not a null: 27 of 119 rostered quarterbacks league-wide carry no '
    'depth-chart row. CONSEQUENCE: on a season-opening board the modelled '
    'split between a club starting quarterback and his backups is not '
    'trustworthy, quarterback-derived markets are CONTAMINATED and '
    'inadmissible, and no QB number here may be compared with a price.')

# B14. WHICH INVARIANT A DRAW-ARTIFACT REFUSAL BELONGS TO.
#
# The hard/diagnostic classification itself lives in ONE place --
# `nfl.prospective.artifact.INVARIANTS` -- and this table only says which
# declared invariant a given refusal code is evidence about. Keeping the two
# apart is deliberate: a reader who wants to know what gates reads the
# registry, and nothing here can change a class.
DRAW_CODE_INVARIANT = {
    'DRAW_SET_EMPTY': 'draw_set_non_empty',
    'DRAW_SET_NO_DRAW_INDEX': 'draw_set_non_empty',
    'DRAW_LAYER_NO_ROWS': 'draw_set_non_empty',
    'DRAW_LAYER_NO_METRICS': 'draw_set_non_empty',
    'DRAW_MATRIX_NO_DRAWS': 'draw_set_non_empty',
    'DRAW_INDEX_RAGGED': 'draw_index_shared',
    'DRAW_INDEX_MANIFEST_MISMATCH': 'draw_index_shared',
    'DRAW_MATRIX_NOT_2D': 'draw_index_shared',
    'DRAW_MATRIX_ROW_MISMATCH': 'draw_index_shared',
    'DRAW_ENCODING_LOSSY': 'draw_encoding_lossless',
    'DRAW_MATRIX_NOT_FINITE': 'draw_encoding_lossless',
}
# Anything not named above is evidence about the container itself.
DRAW_CODE_INVARIANT_DEFAULT = 'draw_artifact_integrity'


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _parse(ts):
    d = _dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def execution_identity(args, source_hashes: dict, code_commit: str) -> str:
    """Changing ANY input hash must change this. Tested."""
    payload = {'season': args.season, 'week': args.week,
               'game_id': args.game_id, 'arm': args.arm,
               'written_at': args.written_at, 'seed': args.seed,
               'code_commit': code_commit,
               # The configuration is part of the identity. Without it a
               # candidate run and a baseline run of the same game would share
               # a run id while containing different numbers.
               'model_configuration': getattr(
                   args, 'model_configuration', None)
               or CAND.PRODUCTION_BASELINE,
               'sources': dict(sorted(source_hashes.items()))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


# Evidence keys a layer uses to say something about its own governance. A key
# absent from a layer's evidence is not defaulted: severity in particular is
# transported only where a layer already declares one, because inventing a
# severity would put an unowned judgement next to a governed value and the two
# would be indistinguishable in the artifact.
_GOVERNANCE_EVIDENCE_KEYS = ('governance', 'warnings', 'spec_version',
                             'severity')


def _governance_facts(got) -> dict:
    """Everything the layers said about their own governance, kept verbatim.

    `got` is [(layer_name, Outcome)] for the layers one declared pipeline
    stage aggregates. The aggregation used to return the layers' values, their
    states and their spec versions and NOT their warnings or their governance,
    so a stage composed of a layer that had raised
    `known limitation: RC1 SIGNAL_WEAK` reported `warnings: []`.

    This function decides nothing. It does not rank a warning, does not judge
    whether one blocks publication, does not merge two layers that said the
    same thing, and does not translate prose into a code. It attaches the name
    of the layer that spoke -- the one fact the aggregation genuinely knows
    and the layer cannot -- and passes the rest through unchanged.

    The composed `spec_version` is derived, not retyped: it is built from the
    spec strings the layers published, so it cannot drift from them. Where no
    layer published one the key is omitted entirely and the pipeline keeps the
    caller's label rather than replacing it with a blank.
    """
    warnings, detail, governance, specs = [], [], [], []
    for n, o in got:
        ev = o.evidence or {}
        for w in (ev.get('warnings') or []):
            # The string stays exactly as the layer wrote it; the layer name
            # is a prefix so two layers raising the same sentence remain two
            # distinguishable facts in the flat list the renderers read.
            warnings.append(f'{n}: {w}')
            rec = {'layer': n, 'warning': w}
            if ev.get('severity') is not None:
                rec['severity'] = ev['severity']
            detail.append(rec)
        if ev.get('governance') is not None:
            rec = {'layer': n, 'governance': ev['governance']}
            if ev.get('severity') is not None:
                rec['severity'] = ev['severity']
            governance.append(rec)
        if ev.get('spec_version'):
            specs.append(f'{n}={ev["spec_version"]}'
                         if len(got) > 1 else str(ev['spec_version']))
    out = {'warnings': warnings, 'warnings_detail': detail,
           'governance': governance}
    if specs:
        out['spec_version'] = '; '.join(specs)
    return out


def code_identity() -> Outcome:
    """A + B + C for this run, from the repository-wide identity module."""
    return CI.code_identity()


def code_commit() -> str:
    '''HEAD and the CONTENT of any dirty source, as one code version string.

    This returned a bare HEAD with no working-tree check, so an artifact could
    name a commit while the code that produced it carried uncommitted changes.
    The first repair added a dirty marker -- `<sha>+dirty[<N>]`, N being the
    line count of `git status --porcelain` -- and got the intent right and the
    mechanism wrong in two opposite directions:

      A COUNT IDENTIFIES NOTHING. Two working trees with the same NUMBER of
      dirty paths produce the same string, so a tree with an edited layers.py
      and a tree with a scratch note were indistinguishable in the sealed
      bytes.

      A RUN MOVED ITS OWN IDENTITY BY WRITING ITS OWN OUTPUTS. Porcelain names
      generated files, so the count rose as the run wrote. WS-E measured it on
      this checkout: +dirty[30] -> 31 -> 32 -> back to 30, with nothing about
      the forecast different across the four calls. That is dF/dD != 0, and it
      gave two bit-identical draw sets two different execution identities.

    `nfl.identity.code_identity` is the repository-wide repair: it hashes the
    CONTENT of the dirty SOURCE files, with the scope declaration inside the
    digest, and excludes every subtree a run writes into. One format whether
    the tree is clean or dirty -- a clean tree is the computed empty-set
    digest, not a second branch -- so no parser needs an unexercised branch.

    A refusal is NAMED rather than flattened to the old bare 'UNKNOWN'. It
    still returns a string, because this function is consumed as one and
    hardening the caller into a refusal is a governance decision, not a
    transport one; what changes here is that the string says which refusal it
    was instead of asserting an identity the run does not have.
    '''
    o = code_identity()
    if o.state is State.PASS:
        return CI.code_version(o.value)
    return f'UNRESOLVED[{o.code}]'


def build(args, fixtures: dict = None) -> dict:
    """Run the pipeline. `fixtures` supplies inputs for a historical dry run."""
    fx = fixtures or {}
    # RESOLVED ONCE, BEFORE THE RUN WRITES ANYTHING. Resolving it twice would
    # reintroduce the defect it replaces in a smaller form: the second call
    # would read a tree this run had already written into.
    fx['_code_identity'] = _ci = code_identity()
    commit = (CI.code_version(_ci.value) if _ci.state is State.PASS
              else f'UNRESOLVED[{_ci.code}]')
    src = fx.get('source_hashes', {})
    run_id = execution_identity(args, src, commit)[:16]
    out_dir = pathlib.Path(args.out_dir) / run_id
    p = PL.Pipeline(run_id=run_id, out_dir=out_dir, arm=args.arm,
                    written_at=args.written_at)

    wrote = _parse(args.written_at)
    kickoff = fx.get('kickoff_utc')

    # --- 1. capture / input validation ---------------------------------
    def _capture():
        if not src:
            return RF.refuse('SOURCE_MISSING', 'capture_validation',
                             'no source captures were supplied', run_id)
        for name, meta in src.items():
            if name not in REG.BY_NAME:
                return RF.refuse('UNAUTHORIZED_INPUT', 'capture_validation',
                                 f'{name} is not in the source registry', run_id)
            if not meta.get('sha256'):
                return RF.refuse('RAW_HASH_MISMATCH', 'capture_validation',
                                 f'{name} carries no sha256', run_id)
            if meta.get('expected_sha256') and \
                    meta['expected_sha256'] != meta['sha256']:
                return RF.refuse('RAW_HASH_MISMATCH', 'capture_validation',
                                 f'{name} hash differs from the recorded one',
                                 run_id)
            got = meta.get('retrieved_at')
            if not got:
                return RF.refuse('SOURCE_CHRONOLOGY_FAILURE',
                                 'capture_validation',
                                 f'{name} has no retrieved_at', run_id)
            if _parse(got) > wrote:
                return RF.refuse('SOURCE_TOO_LATE', 'capture_validation',
                                 f'{name} retrieved at {got}, after '
                                 f'written_at {args.written_at}', run_id)
            if meta.get('schema_ok') is False:
                return RF.refuse('SCHEMA_DRIFT', 'capture_validation',
                                 f'{name} schema does not match', run_id)
        if kickoff and not wrote < _parse(kickoff):
            return RF.refuse('SOURCE_CHRONOLOGY_FAILURE', 'capture_validation',
                             f'written_at {args.written_at} is not before '
                             f'kickoff {kickoff}', run_id)
        if args.arm == 'A' and fx.get('consumes_2026_outcomes'):
            return RF.refuse('ARM_RULE_VIOLATION', 'capture_validation',
                             'arm A may consume no 2026 outcome at any point '
                             'in the season', run_id)
        if fx.get('cold_start_identity_mismatch'):
            return RF.refuse('COLD_START_VIOLATION', 'capture_validation',
                             'the cold-start freeze identity does not match',
                             run_id)
        return Outcome.ok('INPUTS_VALIDATED', value=src,
                          input_hashes={k: v['sha256'] for k, v in src.items()})
    def _appearance_spec(flags):
        """Which appearance mechanism this configuration names. Exactly one.

        Two mechanisms set at once would be two answers to one question, and
        picking the first in some arbitrary order is how a configuration ends
        up running a model nobody asked for. It raises instead.
        """
        named = [n for n, k in (('r7', 'appearance_r7'), ('r8', 'appearance_r8'))
                 if flags.get(k)]
        if len(named) > 1:
            raise ValueError(
                'APPEARANCE_SPEC_AMBIGUOUS: this configuration names '
                f'{named}. One appearance mechanism per configuration.')
        # THE 2026 PANEL IS NOT A FOURTH MECHANISM. It is the frozen one
        # walking a panel that reaches the forecast season -- same
        # coefficients, same featuriser. So it composes with the frozen path
        # and is refused alongside a named alternative rather than silently
        # losing to it, because "which model ran" must have one answer.
        if flags.get('appearance_panel_2026'):
            if named:
                raise ValueError(
                    'APPEARANCE_SPEC_AMBIGUOUS: appearance_panel_2026 '
                    f'extends the FROZEN mechanism and {named} names a '
                    f'different one. Pick one.')
            return 'frozen_2026panel'
        return named[0] if named else 'frozen'

    def _qb_dropback_budgets():
        """{team: dropback draw} for the closure test, or None.

        Keyed by BARE TEAM, which is one of the two shapes `reconcile_team`
        accepts, and a team it cannot find is a refusal there rather than a
        silently skipped check.
        """
        tv = fx.get('_team_volume')
        if not tv:
            return None
        out = {t: v for (m, t), v in tv.items() if m == 'team_dropbacks_part'}
        return out or None

    def _team_volume():
        """THE team-volume draw for this run. One owner, one draw.

        It was drawn twice: the `team_environment` stage called `TV.forecast`
        with NO coupling flags while the candidate path and the engine each
        drew their own COUPLED version. Same quantity, three call sites, and
        under A3G the uncoupled one is a different vector -- so the artifact
        stored team-volume draws the game had never used, and the R2
        apportionment defect (a level apportioned from a budget no game held)
        had a second home one layer up. Memoised here so the number has a
        single owner and every consumer reads the same draw.
        """
        if '_tv_outcome' in fx:
            return fx['_tv_outcome']
        teams = list(fx.get('team_ids') or [])
        m = fx.get('qb_draws', 200)
        gc = (_mode['flags'].get('game_coupling')
              if _mode.get('candidate') else None)
        o = (TV.forecast(args.season, args.week, teams, m=m, seed=args.seed,
                         joint_residuals=True,
                         game_pairs=[(teams[0], teams[1])], game_coupling=gc)
             if gc and gc != 'none' and len(teams) == 2
             else TV.forecast(args.season, args.week, teams, m=m,
                              seed=args.seed))
        fx['_tv_outcome'] = o
        if o.state is State.PASS:
            fx['_team_volume'] = o.value
        return o

    def _candidate_qb():
        """The QB half of the V1 candidate architecture, from the canonical
        entrypoint rather than from an internal-only rehearsal path.

        R2, C0, A3G, SC1 and A1 execute here.

        THIS RUNS BEFORE THE LAYERS THAT DEPEND ON IT, WHICH IS WHY IT IS
        MEMOISED. The declared stage list reports `qb_layer` LAST -- after
        targets_carries, conversion and td_layer -- while C3 needs the
        quarterbacks' throws to form a target budget and A1 needs their
        scrambles to partition the rush plays. Reporting order and dependency
        order are not the same thing, and running the QB half in reporting
        order meant C3 could never be reached from this entrypoint however
        healthy its inputs were. So the result is computed once, on first
        demand, and every later caller -- including the `qb_layer` stage that
        reports it -- receives the same Outcome. Computing it twice would draw
        two different quarterback lines from one declared seed.
        """
        if '_qb_outcome' in fx:
            return fx['_qb_outcome']
        o = _candidate_qb_compute()
        fx['_qb_outcome'] = o
        return o

    def _candidate_qb_compute():
        from nfl.production.nonqb import football_engine as FE
        fl = _mode['flags']
        qbp = [q for q in fx.get('players', [])
               if q.get('position') == 'QB' and q.get('gsis_id')]
        if not qbp:
            # The LAYER's own block, not a production refusal. QB_SLATE_EMPTY
            # is not in refusal.REFUSALS, and routing it through RF.refuse
            # invented an undeclared production refusal code -- caught by the
            # suite's own "every refusal code raised in the production path is
            # declared" check. The baseline path returns the layer outcome
            # here too, so the two paths now agree.
            return Outcome.blocked(
                'QB_SLATE_EMPTY',
                'no quarterback on the roster for this game; an empty slate '
                'is a refusal, not a forecast of nothing',
                cause=Cause.DATA)
        teams = list(fx.get('team_ids') or [])
        m = fx.get('qb_draws', 200)
        # R5-QB. THE ELIGIBILITY FILTER THE QUARTERBACK POOL WAS EXEMPT FROM.
        #
        # R5 filters the non-QB pool on roster status and the comment above it
        # says the QB pool is left untouched. That exemption put a RESERVE-LIST
        # quarterback into a live room: on 2026-09-14 for 2026_01_DEN_KC the
        # pool carried KC's Chris Oladokun, status RES, and the QB3 layer gave
        # him 55.00% of Kansas City's modelled dropbacks against Patrick
        # Mahomes's 37.76%. A player who is not on the active roster cannot
        # take a dropback, so his share is zero by the definition of the event,
        # not by any modelling choice -- the same reasoning `qb_allocation`
        # already applies to an officially inactive quarterback.
        #
        # IT IS THE SAME FILTER, NOT A SECOND ONE. `roster_status.active_pool`
        # is called with the same status map the non-QB half uses, under the
        # same flag, drawn from the same capture and the same chronology cut.
        # No constant is introduced and nothing is reweighted: the room is
        # smaller and QB3 renormalises across whoever remains, exactly as it
        # does for a team that carries two quarterbacks rather than four.
        #
        # THIS IS NOT A FIX FOR THE ORDERING AND IS NOT OFFERED AS ONE.
        # Measured on tonight's rooms: removing Oladokun leaves KC in
        # NO_PREV_PRIMARY_IN_ROOM with Mahomes at 0.5474, Justin Fields at
        # 0.3201, P(Mahomes takes zero dropbacks) = 0.4120 and
        # corr(Mahomes, Fields) = -0.9936 -- the DAL/NYG result of `d652afb`
        # reproduced on a second game. The binding mechanism is the week-1
        # season-boundary incumbent (`QB3_WEEK1_SEASON_BOUNDARY`), which this
        # does not touch. It is applied because a reserve-list quarterback in
        # an eligibility-filtered board is indefensible on its own terms.
        #
        # IT MUST NEVER FALL BACK TO THE UNFILTERED LIST. A status refusal is
        # returned as the layer's outcome, for the reason R5 states: running
        # unfiltered under a filtered label reports a repair that did not
        # happen.
        #
        # SPELLED `eligibility_on` RATHER THAN INLINING THE FLAG READ, because
        # `test_r5_active_pool` locates the NON-QB branch by searching the
        # source for the literal spelling of that flag read in an `if`, and
        # takes the first hit. This block is earlier in the file, so an equal
        # spelling would silently redirect that guard onto this window and the
        # non-QB branch would go unchecked -- a test measuring the wrong code
        # while staying green. The two branches now read differently on
        # purpose; the locator is still fragile and is named in the return.
        eligibility_on = bool(fl.get('active_roster_only'))
        if eligibility_on:
            from nfl.production.nonqb import roster_status as RS
            st = RS.status_map(args.season, args.week, teams,
                               observed_before=args.written_at,
                               kickoff_utc=fx.get('kickoff_utc'))
            if st.state is not State.PASS:
                # SAME RULE AS THE NON-QB HALF: a week with no ACT column is
                # not a week with no quarterbacks. Without this the qb_layer
                # went BLOCKED on 2026 week 2 and the game had no passer.
                # The room is kept whole and each member carries his graded
                # participation probability instead of a hard ACT filter.
                from nfl.production.nonqb import participant_class as PCL
                pcq = PCL.classify(args.season, args.week, qbp,
                                   observed_before=args.written_at)
                if pcq.state is not State.PASS:
                    return pcq
                bq = {r['gsis_id']: r for r in pcq.value if r.get('gsis_id')}
                qkeep = [q for q in qbp
                         if bq.get(q.get('gsis_id'), {})
                         .get('enters_opportunity_pool')]
                qempty = sorted({q.get('team') for q in qbp}
                                - {q.get('team') for q in qkeep})
                if qempty:
                    return Outcome.blocked(
                        'QB_POOL_EMPTIED_BY_ELIGIBILITY',
                        f'every quarterback {qempty} carries is off the game '
                        f'roster, so the club would have nobody to take a '
                        f'dropback. Refused rather than allocating a team '
                        f'dropback share among nobody.',
                        cause=Cause.DATA, teams_emptied=qempty,
                        n_qb_in=len(qbp), n_qb_kept=len(qkeep))
                qbp = [dict(q,
                            participation_prior=bq[q['gsis_id']]
                            .get('participation_prior'),
                            participant_class=bq[q['gsis_id']]
                            .get('participant_class'))
                       for q in qkeep]
                fx['_qb_participant_class'] = {
                    'fallback_from': st.code, 'detail': pcq.detail,
                    'counts': pcq.evidence.get('counts')}
            else:
                qpool = RS.active_pool(qbp, st.value)
                if qpool.state is not State.PASS:
                    return qpool
            # EVERYTHING BELOW READS `qpool`, WHICH ONLY EXISTS WHEN THE
            # ACT COLUMN WAS READABLE. Under the graded fallback the room is
            # kept whole and weighted, so there is no filtered pool to audit
            # and no team can be emptied BY THE FILTER -- the refusal below
            # is about the filter removing a club's last passer, which cannot
            # happen when no filter ran.
            if st.state is State.PASS:
                # A TEAM WHOSE WHOLE ROOM IS INELIGIBLE IS A REFUSAL, NOT AN EMPTY
                # ROOM. `qb_allocation` skips a team with no quarterback and the
                # board would then carry a game one of whose clubs has no passer
                # at all, silently. The non-QB half already refuses this shape
                # (NONQB_TEAM_HAS_NO_PLACEABLE_PLAYER); this says the same thing
                # about quarterbacks.
                had = {q.get('team') for q in qbp}
                left = {q.get('team') for q in qpool.value}
                emptied = sorted(t for t in had if t not in left)
                if emptied:
                    return Outcome.blocked(
                        'QB_POOL_EMPTIED_BY_ELIGIBILITY',
                        f'every quarterback {emptied} carries is off the active '
                        f'roster, so filtering on eligibility would leave the '
                        f'club with nobody to take a dropback. Refused rather '
                        f'than allocating a team dropback share among nobody, '
                        f'and rather than putting the ineligible room back.',
                        cause=Cause.DATA, teams_emptied=emptied,
                        n_qb_in=len(qbp), n_qb_kept=len(qpool.value))
                fx['_r5_qb'] = {
                    k: v for k, v in qpool.evidence.items() if k != 'value'}
                fx['_r5_qb']['roster_status_source'] = st.evidence.get('source')
                fx['_r5_qb']['roster_status_observed_at'] = st.evidence.get(
                    'observed_at')
                fx['_r5_qb']['n_qb_in'] = len(qbp)
                fx['_r5_qb']['n_qb_kept'] = len(qpool.value)
                fx['_r5_qb']['qb_participation_limitation'] = (
                    QB_PARTICIPATION_LIMITATION)
                fx['_r5_qb_applied'] = True
                qbp = list(qpool.value)
        sl = FE.qb_slate(args.season, args.week, qbp, m=m, seed=args.seed,
                         include_cold_start=bool(fl.get('include_cold_start')))
        if sl.state is not State.PASS:
            return sl
        qb = sl.value
        # P0-1. THE TEAM DROPBACK DRAWS, HOISTED ABOVE THE ALLOCATION.
        #
        # `qb_room_v2` allocates an INTEGER dropback count rather than a
        # share, so it needs the team's dropback draws, and `_team_volume` is
        # memoised and independent of the allocation -- it was simply called
        # a few lines later. Hoisting it changes nothing about the draw
        # (same memo, same seed, same coupling); it only makes it available
        # to the allocator that needs it. `qb3` ignores the argument
        # entirely and its call is asserted bit-identical by the suite.
        tv = _team_volume()
        if tv.state is not State.PASS:
            return tv
        _alloc = fl.get('qb_allocator') or 'qb3'
        _tdb = ({t: np.asarray(tv.value[('team_dropbacks_part', t)], float)
                 for t in teams} if _alloc == 'qb_room_v2' else None)
        # THE ARGUMENT WHOSE ABSENCE WAS THE DEFECT. official_inactive_ids
        # reached the non-QB engine only; the QB share pool never saw it.
        # THE CLOCK THE CHRONOLOGY GUARD NEEDS, WHICH NOBODY WAS PASSING.
        #
        # `qb_allocation.allocate` carries a real guard:
        #
        #     for label, bound in (('kickoff', kickoff_utc),
        #                          ('written_at', written_at)):
        #         if bound and got and str(got) >= str(bound):
        #             return Outcome.fail('DEPTH_CHART_CHRONOLOGY_FAILURE', ...)
        #
        # Both parameters default to None and this call site passed neither, so
        # `if bound` was false on every production run and the body has never
        # executed. The guard is correct; it was simply unreachable.
        #
        # What it was guarding: the depth chart is selected by
        # `sorted(glob(...))[-1]` -- lexicographic content-hash order, no clock.
        # Today that resolves to `depth_charts.f66f0c2583dba463.reduced.csv.gz`,
        # retrieved 2026-09-14T16:16:25Z, and **74 of 79 week-1 kickoff targets
        # precede it**. The QB room ordering read from that chart feeds dropback
        # allocation, so a board built for an earlier week-1 game consumed a
        # chart published after its own kickoff.
        #
        # This is the `board.depth_rank` defect one function over, on the same
        # source, and the opposite failure: there the guard fired on every run
        # and a bare `except Exception` destroyed the evidence; here the guard
        # never fired at all. Both are the same lesson -- a guard nobody can
        # see is not a guard.
        #
        # Both values are already in scope and are handed to the neighbouring
        # calls at lines 442-443 and 951-952 in exactly this form.
        qa = FE.QA.allocate(args.season, args.week, teams, qbp, m=m,
                            seed=args.seed,
                            inactive_ids=fx.get('official_inactive_ids'),
                            inactive_provenance=fx.get(
                                'official_inactive_provenance'),
                            allocator=_alloc,
                            team_dropback_draws=_tdb,
                            kickoff_utc=fx.get('kickoff_utc'),
                            written_at=args.written_at)
        if qa.state is not State.PASS:
            return qa
        fx['_qb_allocator'] = _alloc
        # THE VERDICT TRAVELS WITH THE RUN, because the board cannot re-derive
        # it. `qb_inactive_ownership_enforced` used to be read by the product
        # board and written by nobody, so QB_INACTIVE_NOT_CONSUMED could never
        # clear. It is now computed by the layer that owns the share and
        # carried forward from there, never asserted by a caller.
        fx['_qb_ownership'] = qa.evidence.get('qb_inactive_ownership')
        # The room configuration travels with the run for the same
        # reason the ownership verdict does: the board cannot
        # re-derive it, and a reader needs to know whether a QB
        # projection came out of a season-boundary room.
        fx['_qb3_config'] = qa.evidence.get('qb3_configuration')
        qb['allocation'] = qa.value
        gc = fl.get('game_coupling')
        tv = _team_volume()
        if tv.state is not State.PASS:
            return tv
        applied = ['C0'] if fl.get('include_cold_start') else []
        if gc and gc != 'none' and len(teams) == 2:
            applied.append('A3G')
        if fl.get('r2'):
            r2o = FE.apply_r2_level(qb, qa.value, tv, teams)
            if r2o.state is not State.PASS:
                return r2o
            qb = r2o.value
            applied.append('R2')
        # A1 NEEDS ONLY THE CARRY BUDGET AND THE SCRAMBLES, both of which
        # exist here, so it runs on this path even while the appearance layer
        # is deferred. C3 does need the receiving budget and does not.
        not_reached = []
        if fl.get('rushing_a1'):
            from nfl.production.nonqb import rushing_a1 as RA1
            from nfl.production.nonqb import scramble_coherence as SC1
            scr = {t: np.asarray(
                [qb['draws']['scr'][i] for i in
                 qb['index_by_team'].get(t, [])], float).sum(0)
                if qb['index_by_team'].get(t) else np.zeros(m)
                for t in teams}
            # SC1. A scramble IS a rush attempt, so carries >= scrambles holds
            # in 3,230 of 3,230 historical team-games. The model draws the two
            # on one index from independent randomness, so their tails can
            # cross. SC1 chooses WHICH DRAW INDEX RECEIVES WHICH CARRY VALUE --
            # a permutation, so the carry marginal is invariant element for
            # element and the scramble draw is not touched at all. Minimal
            # swaps, so A3G's pairing survives wherever it was not the problem.
            # R11. THE WHOLE COMPOSITION IN ONE CALL, OR THE THREE STEPS
            # SEPARATELY, AND THE FLAG DECIDES WHICH.
            #
            # Under R9 these three lines each looked right on their own and
            # the composition did not: SC1 bounded the carry level by the
            # SCRAMBLES while the named rush owners include the quarterback's
            # DESIGNED runs too; `allocate` was called without
            # `qb_designed_rush`, so A1 drew a second answer to a quantity the
            # QB layer had already drawn; and the level sealed below was D1's
            # raw continuous draw rather than the integerised, permuted one
            # the partition consumed. Measured on sealed board
            # 96954efc523bd7d3: named owners above the team's own carry level
            # in 149 of 1,000 DEN draws and 148 of 1,000 KC draws, by up to
            # 6.1219 and 9.6915 carries, while the RB deal alone was over the
            # gate tolerance in ZERO draws on both clubs.
            #
            # `rushing_a1.compose_rush_ownership` is those three steps in the
            # order that makes the bound an identity. Nothing is clipped,
            # truncated, renormalised or deleted. The R9 path below is left
            # EXACTLY as it was, byte for byte, so every sealed R9 board stays
            # reproducible and the two configurations differ in one component.
            _single = bool(fl.get('rush_single_owner'))
            if _single:
                ro = {t: np.asarray(
                    [qb['draws']['rush_opp'][i] for i in
                     qb['index_by_team'].get(t, [])], float).sum(0)
                    if qb['index_by_team'].get(t) else np.zeros(m)
                    for t in teams}
                comp = RA1.compose_rush_ownership(
                    args.season, args.week, teams,
                    team_carry_level={
                        t: np.asarray(tv.value[('team_carries', t)], float)
                        for t in teams},
                    qb_scrambles=scr, qb_rush_opportunity=ro,
                    m=m, seed=args.seed, game_id=args.game_id,
                    level_rounding='round_half_even')
                if comp.state is not State.PASS:
                    return comp
                sc1 = comp.value['sc1']
                fx['_sc1'] = sc1
                # THE LEVEL THE BOARD PUBLISHES IS THE LEVEL THAT WAS
                # PARTITIONED. Sealing D1's raw vector beside an allocation
                # built on a different one is the stored-vector defect that
                # keeps `team_qb_rush_opportunity_within_team_carries` a
                # diagnostic instead of a gate.
                fx['_published_team_carries'] = comp.value[
                    'team_carries_published']
                _inv_sc1 = fx.setdefault('_inv', {})
                _inv_sc1['scramble_carry_coherence'] = Outcome.ok(
                    'SC1_COHERENT', value=True,
                    detail='carries >= the quarterbacks` WHOLE rush '
                           'opportunity in every draw -- scrambles and '
                           'designed runs both -- by permutation of the carry '
                           'draw index; no value changed',
                    total_swaps=sum(int(v.get('n_swaps', 0))
                                    for v in sc1.values()),
                    bound='qb_rush_opportunity', teams=len(sc1))
                applied.append('SC1')
                a1 = Outcome.ok(
                    comp.code, value=comp.value['allocation'],
                    detail=comp.detail,
                    **{k: v for k, v in comp.evidence.items()
                       if k != 'value'})
                fx['_rushing_a1'] = a1
                fx['_rush_composition'] = {
                    k: v for k, v in comp.evidence.items() if k != 'value'}
                _inv_a1 = fx.setdefault('_inv', {})
                _inv_a1['rushing_single_owner'] = a1
                # 'R11' is NOT appended here. `applied` carries the
                # engine-flag components (R2, C0, C3, A3G, SC1, A1); the
                # configuration-level repairs R5-R11 are declared in
                # `candidate_components` and in `model_configuration`,
                # and inventing a second place to name them is how two
                # lists of the same thing start disagreeing.
                applied.append('A1')
            else:
                car, sc1 = {}, {}
                for t in teams:
                    o = SC1.couple(scr[t],
                                   np.asarray(tv.value[('team_carries', t)],
                                              float))
                    if o.state is not State.PASS:
                        return o
                    car[t] = o.value
                    sc1[t] = {k: v for k, v in o.evidence.items()
                              if k != 'value'}
                fx['_sc1'] = sc1
                _inv_sc1 = fx.setdefault('_inv', {})
                _inv_sc1['scramble_carry_coherence'] = Outcome.ok(
                    'SC1_COHERENT', value=True,
                    detail='carries >= scrambles in every draw, by '
                           'permutation of the carry draw index; no value '
                           'changed',
                    total_swaps=sum(int(v.get('n_swaps', 0))
                                    for v in sc1.values()),
                    teams=len(sc1))
                applied.append('SC1')
                a1 = RA1.allocate(
                    args.season, args.week, teams, car,
                    scr, m=m, seed=args.seed, game_id=args.game_id,
                    level_rounding='round_half_even')
                if a1.state is not State.PASS:
                    return a1
                fx['_rushing_a1'] = a1
                _inv_a1 = fx.setdefault('_inv', {})
                _inv_a1['rushing_single_owner'] = a1
                applied.append('A1')
        # C3 IS NOT ADJUDICATED HERE. It is reached inside the non-QB chain
        # or it is not, and only that chain can say which; this used to record
        # `not reached` unconditionally, which was accurate only for as long
        # as the chain could not run at all.
        fx['qb_rows'] = qb['rows']
        fx['_qb_draws_out'] = qb['draws']
        # THE QB OBJECT ITSELF, because C3 needs the throws and the engine
        # needs the object rather than the draws alone.
        fx['_qb_object'] = qb
        fx['_candidate_applied'] = sorted(applied)
        fx['_candidate_not_reached'] = sorted(not_reached)
        # EVERY DECLARED HARD INVARIANT GETS A VERDICT ON THIS PATH TOO.
        # The candidate path first shipped without them and the B14 gate
        # refused all 16 games with INVARIANT_VERDICT_MISSING -- the guard
        # working, on my own incomplete path. Silence is not a state.
        _inv = fx.setdefault('_inv', {})
        ident = QBV1.identity_check(qb['draws'])
        _inv['qb_dropback_identity'] = ident
        if ident.state is not State.PASS:
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'qb_layer',
                             ident.detail, run_id)
        acct = QBACC.reconcile_draws(qb['draws'])
        _inv['qb_per_draw_accounting'] = acct
        if acct.state is not State.PASS:
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'qb_layer',
                             f'{acct.code}: {acct.detail}', run_id)
        team = QBACC.reconcile_team(
            qb['draws'], qb['rows'],
            team_rush_draws=fx.get('team_rush_draws'),
            team_rushes_realised=fx.get('team_rushes_realised'),
            team_dropback_draws=_qb_dropback_budgets(),
            integer_level=bool(fl.get('r2')))
        _inv['qb_team_accounting'] = team
        _inv['qb_inactive_owns_nothing'] = QBACC.assert_inactive_qbs_own_nothing(
            qb['draws'], qb['rows'], fx.get('official_inactive_ids'))
        if _inv['qb_inactive_owns_nothing'].state is State.FAIL:
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'qb_layer',
                             f"{_inv['qb_inactive_owns_nothing'].code}: "
                             f"{_inv['qb_inactive_owns_nothing'].detail}",
                             run_id)
        fx['_qb_team_warnings'] = list(team.evidence.get('warnings') or [])
        if team.state is not State.PASS:
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'qb_layer',
                             f'{team.code}: {team.detail}', run_id)
        fx['_qb_accounting'] = {'per_draw': acct.value, 'team': team.value}
        return Outcome.ok(
            'QB_LAYER_OK', value=qb['draws'],
            model_configuration=_mode['mode'],
            candidate_components_applied=sorted(applied),
            candidate_components_not_reached=sorted(not_reached),
            n_qb_games=len(qb['rows']),
            qb_level_owner=(qb.get('r2') or {}).get('level_owner'),
            # THE SAME LAYER'S LIMITATIONS ON BOTH PATHS.
            #
            # The BASELINE return below carries
            # `warnings=[f'known limitation: {k}' for k in
            # QBV1.KNOWN_LIMITATIONS]` and this candidate return carried none,
            # so the stage table read "no warnings" for the LESS validated of
            # the two configurations. Both paths run QB V1, so both paths
            # declare QB V1's limitations; the list is read from the layer,
            # not restated here.
            warnings=[f'known limitation: {k}'
                      for k in QBV1.KNOWN_LIMITATIONS]
            + list(team.evidence.get('warnings') or []),
            warnings_detail=(
                [{'layer': 'qb_v1', 'warning': f'known limitation: {k}'}
                 for k in QBV1.KNOWN_LIMITATIONS]
                + [{'layer': 'qb_team_accounting', 'warning': w}
                   for w in (team.evidence.get('warnings') or [])]))

    # MODEL CONFIGURATION, RESOLVED ONCE AND CARRIED. An unknown name is a
    # refusal, never a fall-back to the baseline -- falling back would run the
    # PROMOTED model while the operator believed they were running the
    # candidate, which fails in the dangerous direction.
    _mode_o = CAND.resolve(getattr(args, 'model_configuration', None))
    if _mode_o.state is not State.PASS:
        return {'run_id': run_id, 'status': 'REFUSED',
                'stages': [{'stage': 'capture_validation', 'state': 'FAIL',
                            'code': _mode_o.code, 'detail': _mode_o.detail}],
                'publication': {'code': 'NFL1_NOT_AUTHORIZED'},
                'model_configuration': getattr(
                    args, 'model_configuration', None)}
    _mode = _mode_o.value

    p.run_stage('capture_validation', _capture,
                declared_inputs=list(src), spec_version=PL.PIPELINE_VERSION)

    # --- 2. identity resolution ----------------------------------------
    def _identity():
        players = fx.get('players', [])
        if not players:
            return RF.refuse('IDENTITY_UNRESOLVED', 'identity_resolution',
                             'no players supplied for the slate', run_id)
        bad = [q for q in players if not q.get('gsis_id')]
        # AN UNIDENTIFIABLE PLAYER IS EXCLUDED AND NAMED, NOT SILENTLY DROPPED
        # AND NOT GUESSED. The guard's purpose is that we never forecast a
        # player we cannot identify and never fuzzy-match a name; excluding him
        # satisfies both. Refusing the whole game does not: measured on the
        # 2026 week 1 roster, ONE practice-squad NYJ running back with no
        # gsis_id -- present in all three roster vintages, so upstream rather
        # than a capture defect -- blocked an entire game's forecast.
        #
        # The escape hatch is bounded. Above EXCLUSION_LIMIT the roster feed is
        # broken rather than merely incomplete, and the run refuses.
        if players and len(bad) / len(players) > EXCLUSION_LIMIT:
            return RF.refuse('IDENTITY_UNRESOLVED', 'identity_resolution',
                             f'{len(bad)} of {len(players)} player(s) have no '
                             f'gsis_id, above the {EXCLUSION_LIMIT:.0%} limit; '
                             f'that is a broken roster feed, not an incomplete '
                             f'one. Fuzzy name matching is forbidden.', run_id)
        resolved = [q for q in players if q.get('gsis_id')]
        if not resolved:
            return RF.refuse('IDENTITY_UNRESOLVED', 'identity_resolution',
                             'no player on the slate carries a gsis_id',
                             run_id)
        fx['_excluded_unidentified'] = [
            {'team': q.get('team'), 'position': q.get('position'),
             'reason': 'NO_GSIS_ID'} for q in bad]
        players = resolved
        if fx.get('game_missing'):
            return RF.refuse('REQUIRED_GAME_MISSING', 'identity_resolution',
                             'a requested game is absent from the schedule',
                             run_id)
        return Outcome.ok('IDENTITY_RESOLVED', value=players,
                          n_resolved=len(players), n_excluded=len(bad),
                          excluded=fx['_excluded_unidentified'],
                          warnings=([f'{len(bad)} player(s) excluded: no '
                                     f'gsis_id'] if bad else []))
    p.run_stage('identity_resolution', _identity, declared_inputs=['players'])

    # --- 3..10 modelling stages ----------------------------------------
    # The five layers that exist in nfl/production/nonqb and are gated on a
    # captured input rather than on being unwritten.
    NONQB_CHAIN = ('appearance', 'participation', 'targets_carries',
                   'conversion', 'td_layer')

    def _nonqb_chain():
        """The whole non-QB chain, from the ONE layer that owns its wiring.

        THIS USED TO CALL EACH LAYER WITH EMPTY PLACEHOLDERS:

            LY.targets_carries(pa, 'targets', [], [], ([], []), [], {}, ...)
            LY.receiving_conversion(tc, [], {}, [], [], _ord)
            LY.td_layer(cv, [], {}, [], [], _ord)

        Every one of those arguments has an owner. `{}` is the frozen P4C
        parameter block, `[]` the class point forecast, `([], [])` the group
        layout the allocator partitions over, and the later `{}` are the RC1
        and TD2 priors. Supplied empty, the chain could only ever raise -- and
        it did, `KeyError: 'add_pool'`, the first time an injury feed was
        complete enough for `appearance` to pass and the stage to be reached
        at all. Until then it was NOT_APPLICABLE for an unrelated upstream
        reason, so a chain that could not run looked wired for as long as it
        was never asked to.

        The fix is not to fill the placeholders here. `football_engine`
        already owns this composition -- it is the accepted V1 architecture,
        it is what the rehearsal exercises, and it resolves each argument from
        `slate_fits`, the appearance layer and the team-volume layer. Building
        a second copy of that wiring in the entrypoint would give every one of
        these inputs two owners, which is the defect this project pays for
        most. So the entrypoint delegates and reports.

        Runs once; every stage then reports its own layer's real Outcome.
        """
        if '_nonqb' in fx:
            return fx['_nonqb']
        try:
            from nfl.production.nonqb import football_engine as FE
        except Exception as e:                                # noqa: BLE001
            o = Outcome.blocked(
                'NONQB_LAYER_IMPORT_FAILED', f'{type(e).__name__}: {e}',
                cause=Cause.DEPENDENCY)
            fx['_nonqb'] = {'fatal': o}
            return fx['_nonqb']

        players = fx.get('players') or []
        teams = list(fx.get('team_ids') or [])
        m = fx.get('qb_draws', 200)
        fl = _mode['flags']

        # THE 2026 WEEK-1 PARTICIPATION ROWS ARE OPT-IN, PER CANDIDATE.
        # Set from the resolved mode's flags so the arm that consumes the
        # approximated numerator is the arm that declared it. R9 and every
        # frozen arm leave it False and are byte-identical to before.
        from nfl.production.nonqb import participation_prior as _PP
        _PP.set_include_2026w1(bool(fl.get('include_2026w1_participation')))

        if not players:
            o = Outcome.blocked(
                'NONQB_PLAYER_SET_EMPTY',
                'no player was supplied for this game, so there is no one to '
                'allocate opportunity among. An empty roster is a refusal, '
                'not an allocation of nothing.', cause=Cause.DATA)
            fx['_nonqb'] = {'fatal': o}
            return fx['_nonqb']

        # THE FRAME IS CHECKED BEFORE THE ENGINE IS ASKED TO USE IT.
        # Allocation partitions opportunity BY POSITION WITHIN A TEAM, so a
        # player carrying neither is not a player this chain can place. Left
        # unchecked the engine reaches them deep inside a grouping step and
        # raises a KeyError, which is the same unnamed-crash shape this whole
        # repair exists to remove -- one layer further in.
        need = ('gsis_id', 'position', 'team')
        thin = [q for q in players if not all(q.get(k) for k in need)]
        if thin:
            # THE REFUSAL IS SCOPED TO THE PLAYER, NOT THE GAME.
            #
            # This used to refuse the whole non-QB chain, and on 2026-09-13 it
            # did: ONE player of 190 carried no position, and NYJ@TEN produced
            # no running back and no receiver projection for either club. Two
            # other games lost their boards the same way for a different
            # missing field. A player who cannot be placed is still only one
            # player, and the rest of the frame is not damaged by his absence.
            #
            # `identity_resolution` ALREADY established this policy for a
            # missing gsis_id, with its own declared EXCLUSION_LIMIT: exclude,
            # name, and refuse only when the count says the feed is broken
            # rather than incomplete. This applies that same policy to the
            # same class of defect two fields wider. It is not a new rule and
            # it introduces no new constant.
            limit = EXCLUSION_LIMIT
            if len(thin) / len(players) > limit:
                o = Outcome.blocked(
                    'NONQB_PLAYER_FRAME_INCOMPLETE',
                    f'{len(thin)} of {len(players)} player(s) carry no '
                    f'{"/".join(need)}, above the {limit:.0%} limit. That is '
                    f'a broken roster feed rather than an incomplete one, so '
                    f'it is refused instead of excluded.',
                    cause=Cause.DATA,
                    n_incomplete=len(thin), n_players=len(players),
                    limit=limit,
                    example=[{k: q.get(k) for k in need} for q in thin[:3]])
                fx['_nonqb'] = {'fatal': o}
                return fx['_nonqb']
            keep = [q for q in players if all(q.get(k) for k in need)]
            # A TEAM THAT LOSES EVERY PLAYER IS A REAL REFUSAL. Allocation
            # partitions opportunity WITHIN a team, so a team with nobody left
            # has no partition to make and excluding down to it would invent
            # one.
            left = {q['team'] for q in keep}
            empty = [t for t in teams if t not in left]
            if empty:
                o = Outcome.blocked(
                    'NONQB_TEAM_HAS_NO_PLACEABLE_PLAYER',
                    f'excluding {len(thin)} unplaceable player(s) would leave '
                    f'{empty} with nobody to allocate opportunity among. '
                    f'Refused rather than allocating within an empty team.',
                    cause=Cause.DATA, teams_emptied=empty,
                    n_excluded=len(thin))
                fx['_nonqb'] = {'fatal': o}
                return fx['_nonqb']
            fx.setdefault('_excluded_unidentified', []).extend(
                {'team': q.get('team'), 'position': q.get('position'),
                 'gsis_id': q.get('gsis_id'),
                 'missing_fields': [k for k in need if not q.get(k)],
                 'reason': 'NONQB_FRAME_FIELD_MISSING'} for q in thin)
            players = keep

        # THE DERIVED ARTIFACTS FIRST, through their declared owner. The QB
        # stage already gated on this; the non-QB chain reached the same
        # artifacts through `p4c_params` and got a FileNotFoundError instead
        # of a named refusal.
        _da = DERIVED.artifacts()
        if _da.state is not State.PASS:
            fx['_nonqb'] = {'fatal': RF.refuse(
                'MODEL_ARTIFACT_MISSING', 'appearance',
                f'{_da.code}: {_da.detail}'[:300], run_id)}
            return fx['_nonqb']
        # R5. THE ALLOCATION POOL, FILTERED TO THE ACTIVE ROSTER.
        #
        # Applied HERE, before slate_fits and before the engine, because it is
        # a statement about who is eligible to receive opportunity at all --
        # not a correction to an allocation already made. A downstream
        # reweighting would be compensating for an upstream error.
        #
        # The QB pool is untouched: quarterback allocation does not run through
        # the P4C simplex, its shares are already correct (the starters hold
        # 88-91% of their teams' attempts), and changing it would disturb the
        # control this repair is measured against.
        if fl.get('active_roster_only'):
            # R2 PATCH 1, APPLIED. `roster_status.active_pool` answers ONE
            # question -- is he on the active roster -- and reads every other
            # adverse determination as silence. The gate answers the question
            # actually being asked, over four ranked authorities, and it
            # removes an ineligible player at CHOICE-SET CONSTRUCTION rather
            # than allocating to him and zeroing him afterwards. R2 measured
            # what the difference costs: allocate-then-zero moves 17.60 units
            # of share onto his team-mates; the gate leaves him with none.
            #
            # The evidence keys `_r5` carried are preserved, because callers
            # downstream read them and a repair that silently renames its own
            # audit trail is a repair nobody can check.
            from nfl.production.nonqb import roster_status as RS
            from nfl.production import eligibility_gate as EG
            st = RS.status_map(args.season, args.week, teams,
                               observed_before=args.written_at,
                               kickoff_utc=fx.get('kickoff_utc'))
            if st.state is not State.PASS:
                # NO ACT COLUMN FOR THIS WEEK IS NOT AN EMPTY LEAGUE.
                #
                # This was `fatal`, and on 2026 week 2 it fired: no raw
                # weekly-roster capture carries `status` for week 2, because
                # the vintage reduction drops the column, so status_map
                # returned ROSTER_STATUS_EMPTY and DET-BUF produced no running
                # back, no receiver and no tight end for either club. Missing
                # evidence about roster STATUS was being read as a claim that
                # the participant UNIVERSE is empty.
                #
                # The fallback is NOT an unfiltered membership pool -- that
                # recreates the dilution R5 exists to prevent, and it was
                # measured before being rejected: league week-2 skill
                # membership is 810 rows of which only 487 were ACT, and DET's
                # contains a RETIRED player. Instead every member is placed in
                # a graded participation class and carries P(takes an
                # offensive snap), so an impossible player contributes almost
                # nothing while nobody is deleted from the universe.
                from nfl.production.nonqb import participant_class as PCL
                pc = PCL.classify(args.season, args.week, players,
                                  observed_before=args.written_at)
                if pc.state is not State.PASS:
                    fx['_nonqb'] = {'fatal': pc}
                    return fx['_nonqb']
                # OFF THE GAME ROSTER MEANS OUT OF THE POOL, NOT A TINY
                # SHARE. Weighting a practice-squad player by a smoothed
                # observation rate gave him a direct route to a target without
                # ever entering a lawful game-day state. He needs a ROSTER
                # TRANSITION first, and its probability is not identified --
                # `official_transactions` has no endpoint. So he is held out of
                # the opportunity pool and the branch stays visible.
                by_id = {r['gsis_id']: r for r in pc.value if r.get('gsis_id')}
                pool_ids = {g for g, r in by_id.items()
                            if r.get('enters_opportunity_pool')}
                held = [q for q in players
                        if q.get('gsis_id') not in pool_ids]
                kept = [q for q in players if q.get('gsis_id') in pool_ids]
                # A TEAM WITH NOBODY LEFT IS A REFUSAL, not an empty partition.
                emptied = sorted({q.get('team') for q in players}
                                 - {q.get('team') for q in kept})
                if emptied:
                    fx['_nonqb'] = {'fatal': Outcome.blocked(
                        'PARTICIPANT_POOL_EMPTIED_BY_ELIGIBILITY',
                        f'{emptied} has no player on the game roster, so '
                        f'there is nobody to allocate opportunity among. '
                        f'Refused rather than allocating within an empty '
                        f'team or putting the off-roster players back.',
                        cause=Cause.DATA, teams_emptied=emptied,
                        n_in=len(players), n_kept=len(kept))}
                    return fx['_nonqb']
                players = [dict(q,
                                participation_prior=by_id[q['gsis_id']]
                                .get('participation_prior'),
                                participant_class=by_id[q['gsis_id']]
                                .get('participant_class'),
                                eligibility_state=by_id[q['gsis_id']]
                                .get('eligibility_state'))
                           for q in kept]
                fx['_participant_class'] = {
                    k: v for k, v in pc.evidence.items() if k != 'value'}
                fx['_participant_class']['fallback_from'] = st.code
                fx['_participant_class']['n_members'] = len(by_id)
                fx['_participant_class']['n_in_opportunity_pool'] = len(kept)
                fx['_participant_class']['n_held_off_roster'] = len(held)
                fx['_participant_class']['held_off_roster'] = [
                    {'gsis_id': q.get('gsis_id'), 'team': q.get('team'),
                     'position': q.get('position'),
                     'participant_class': by_id.get(q.get('gsis_id'), {})
                     .get('participant_class'),
                     'reason': 'REQUIRES_ROSTER_TRANSITION_PROBABILITY_'
                               'THAT_IS_NOT_IDENTIFIED'}
                    for q in held]
                fx['_participant_class']['detail'] = pc.detail
                # The gate below still runs: official inactives and the injury
                # report are ranked authorities and they still exclude.
                # This adds the class the gate cannot see; it replaces nothing.

            # CURRENT-STATE AVAILABILITY, ON TOP OF ROSTER MEMBERSHIP.
            #
            # Roster class answers "is he on the game roster". It does not
            # answer "has the club said he is out this week", and nothing
            # else on this path did either: every 2026 official injury
            # capture carries week 1 only, so a week-2 board had NO injury
            # evidence at all and Ty Johnson was allocated 4.1 carries on a
            # week the feed lists him OUT.
            #
            # Only TERMINAL states act -- OUT, injured reserve, PUP/NFI,
            # suspension, an official game-day inactive. Doubtful and
            # Questionable are preserved and move nobody: no calibrated
            # transition exists for them here, and turning a probability into
            # a certainty because the word sounds bad is the fabrication this
            # project forbids. Absence from the feed is NO_ITEM and is not
            # evidence of health.
            if (fl or {}).get('availability_feed'):
                from nfl.production.nonqb import availability_feed as AVF
                # NAMES COME FROM THE RESOLVER, NOT FROM THE PLAYER DICT.
                # At this point in the pipeline a player row carries no
                # `name` -- display names are resolved later -- so keying the
                # feed on it returned UNRESOLVED_IDENTITY for all 108 and
                # removed nobody. The feed is name-keyed because the source
                # has no gsis_id, so it needs the same resolver the board
                # prints from.
                try:
                    _rn = NAMES.lookup(args.written_at) or {}
                except Exception:                            # noqa: BLE001
                    _rn = {}
                _nm = {q['gsis_id']: (_rn.get(q['gsis_id']) or q.get('name'))
                       for q in players if q.get('gsis_id')}
                _av = AVF.states(args.written_at, _nm)
                if _av.state is State.PASS:
                    _out_ids = {g for g, v in _av.value.items()
                                if v.get('availability') == 'UNAVAILABLE'}
                    _before = len(players)
                    _removed = [q for q in players
                                if q.get('gsis_id') in _out_ids]
                    if _removed:
                        players = [q for q in players
                                   if q.get('gsis_id') not in _out_ids]
                    _ev = _av.as_dict()['evidence']
                    fx['_availability'] = {
                        k: v for k, v in _ev.items() if k != 'value'}
                    fx['_availability']['n_players_considered'] = _before
                    fx['_availability']['n_removed'] = len(_removed)
                    # NAMED, WITH THE EVIDENCE THAT REMOVED HIM. A player who
                    # vanishes from a board without a record is worse than one
                    # who should not have been on it.
                    fx['_availability']['removed'] = [
                        {'gsis_id': q.get('gsis_id'),
                         'name': _nm.get(q.get('gsis_id')) or q.get('name'),
                         'team': q.get('team'), 'position': q.get('position'),
                         **{k: _av.value[q['gsis_id']].get(k)
                            for k in ('designation_text', 'published_at',
                                      'retrieved_at', 'source', 'authority',
                                      'detail')}}
                        for q in _removed]
                    fx['_availability']['opportunity_redistribution'] = (
                        'NOT REASSIGNED BY HAND. A removed player simply is '
                        'not in the allocation, so the existing football '
                        'mechanisms -- the A1 category multinomial and the '
                        'P4C simplex over the remaining pool -- deal his '
                        'share among the players who are.')
                else:
                    fx['_availability'] = {
                        'state': f'{_av.state.value}[{_av.code}]',
                        'detail': _av.detail[:300]}
            nonqb = [q for q in players if q.get('position') != 'QB']
            qbs = [q for q in players if q.get('position') == 'QB']
            snap = EG.snapshot(
                args.season, args.week, teams, nonqb,
                kickoff_utc=fx.get('kickoff_utc'),
                observed_before=args.written_at,
                game_id=args.game_id,
                # None means NO LIST WAS AVAILABLE. () would mean a list was
                # read and named nobody. They are different facts and the
                # gate is entitled to tell them apart.
                official_inactive_ids=fx.get('official_inactive_ids'))
            if snap.state is not State.PASS:
                fx['_nonqb'] = {'fatal': snap}
                return fx['_nonqb']
            pool = EG.choice_set(nonqb, snap)
            if pool.state is not State.PASS:
                fx['_nonqb'] = {'fatal': pool}
                return fx['_nonqb']
            players = qbs + list(pool.value)
            fx['_eligibility'] = {k: v for k, v in snap.evidence.items()
                                  if k != 'value'}
            fx['_r5'] = {k: v for k, v in pool.evidence.items()
                         if k != 'value'}
            fx['_eligibility_gate_applied'] = True
            fx['_r5']['roster_status_source'] = st.evidence.get('source')
            fx['_r5']['roster_status_observed_at'] = st.evidence.get(
                'observed_at')
            # RECORDED ON A KEY THE QB HALF CANNOT OVERWRITE. `_candidate_qb`
            # rewrites `_candidate_applied` wholesale when it runs, which is
            # after this, so a marker written there is silently lost and the
            # artifact then claims R5 was not applied on a run where it was.
            fx['_r5_applied'] = True

        # R6. THE ROLE-CONDITIONAL PRIOR, built from history strictly earlier
        # than this week and handed to the class point forecast. Absent -- the
        # V1 and R5 path -- slate_fits is called exactly as before.
        role_priors, tiers = None, None
        if fl.get('role_prior'):
            from nfl.production.nonqb import role_prior as RP
            import p4c_build as _PB
            import p4c_lib as _PL
            panel = _PB.load_panel()
            cut = args.season * 100 + args.week
            role_priors = {}
            for _cls, _share in (('targets', 'target_share'),
                                 ('carries', 'carry_share')):
                o = RP.build(panel, _share, _PL.CLASSES[_cls]['pos'], cut)
                if o.state is not State.PASS:
                    fx['_nonqb'] = {'fatal': o}
                    return fx['_nonqb']
                role_priors[_cls] = o.value
                fx.setdefault('_r6', {})[_cls] = {
                    k: v for k, v in o.evidence.items() if k != 'value'}
            # Tier from trailing snap share, with the captured depth chart as
            # the named fallback for players who have none.
            # R6-CLOCK, REPAIRED. This read `depth_rank(season, week, teams)`
            # with no `as_of`, inside `except Exception: dr = {}`. There is no
            # `vintage_selector.clock(...)` block anywhere in the production
            # path, so the selector refused -- correctly, every single time --
            # with VINTAGE_CLOCK_UNRESOLVED, and the bare except destroyed the
            # evidence that it had. `assign_tiers` has therefore never seen a
            # depth rank on any board in the corpus: measured on tonight's
            # pool the basis counter reads `trailing_snap_share` 22 /
            # `no_information_lowest_tier` 5, where a supplied rank gives
            # `shrunk_trailing_and_depth` 22 / `depth_chart` 5.
            #
            # It is worth being exact about what repairing it buys, because it
            # is less than it looks: on tonight's 27-player pool the supplied
            # rank changes ZERO tiers in all six rooms. The anchor moves every
            # score and `assign_tiers` exports rank, which absorbs it. The
            # repair is here because a guard that fires on every run and is
            # never seen is a broken guard, not because it moves tonight.
            #
            # The cut is the one the forecast itself declares. A refusal is
            # now RECORDED rather than swallowed: `dr` still falls back to
            # empty, because an absent chart is a real state the mechanism
            # already handles, but the artifact says which state it was in.
            dr, dr_ev = {}, None
            from nfl.product import board as _PBRD
            from nfl.production.nonqb import vintage_selector as _VS
            _dro = _PBRD.depth_rank_outcome(
                args.season, args.week, teams,
                as_of=_VS.as_of_cut(fx.get('kickoff_utc'), args.written_at))
            if _dro.state is State.PASS:
                for k, v in _dro.value.items():
                    dr[k] = v[1]
                dr_ev = {'state': 'PASS', 'code': _dro.code,
                         'n_players': len(dr),
                         'as_of': _dro.evidence.get('as_of')}
            else:
                dr_ev = {'state': _dro.state.value, 'code': _dro.code,
                         'detail': str(_dro.detail)[:300], 'n_players': 0}
            fx['_r6']['depth_rank'] = dr_ev
            at = RP.assign_tiers(
                [q for q in players if q.get('position') != 'QB'],
                role_priors['targets'], depth_rank=dr)
            tiers = at['tier']
            import collections as _c
            fx['_r6']['tier_basis'] = dict(_c.Counter(at['basis'].values()))
            # R3 PATCH 1, APPLIED. D2 asked for `tier` and `basis` on the row;
            # a basis COUNTER cannot answer which player was placed on what
            # evidence. `tier_degraded` is the one to read first: anything but
            # False means the repaired single-scale ordering did not run and
            # the board is carrying the old two-pass defect.
            fx['_r6']['tier_detail'] = at['detail']
            fx['_r6']['tier_ordering'] = at['ordering']
            fx['_r6']['tier_degraded'] = at['degraded']
            fx['_r6_applied'] = True

        # R7. THE APPEARANCE FRAME REPAIR. Nothing is computed here: the flag
        # selects which mechanism `layers.appearance` runs, and the evidence
        # comes back on the layer outcome. Recorded now so the marker survives
        # a halt before the engine reaches the appearance layer.
        if fl.get('appearance_r7'):
            from nfl.production.nonqb import appearance_r7 as _AR7
            fx['_r7'] = {'spec_version': _AR7.SPEC_VERSION,
                         'unsupported_cell': _AR7.UNSUPPORTED_CELL,
                         'observed_before': str(args.written_at)}
            fx['_r7_applied'] = True
        if fl.get('appearance_r8'):
            from nfl.production.nonqb import appearance_r8 as _AR8
            _k = _AR8.reliability_k(_AR8.enriched_frame().value,
                                    cut=args.season * 100)
            fx['_r8'] = {'spec_version': _AR8.SPEC_VERSION,
                         'unsupported_cell': _AR8.UNSUPPORTED_CELL,
                         'observed_before': str(args.written_at),
                         'k': (round(_k.value, 6)
                               if _k.state is State.PASS else None),
                         'k_state': f'{_k.state.value}[{_k.code}]'}
            fx['_r8_applied'] = True

        try:
            fits = FE.slate_fits(args.season, args.week, players,
                                 role_priors=role_priors, tiers=tiers)
        except Exception as e:                                # noqa: BLE001
            fits = Outcome.fail(
                'SLATE_FITS_RAISED', f'{type(e).__name__}: {e}'[:400])
        if fits.state is not State.PASS:
            # NAMED, and it names WHICH fit. `slate_fits` already refuses with
            # the failing artifact in its detail; passing it straight through
            # keeps that rather than flattening it to "inputs unavailable".
            fx['_nonqb'] = {'fatal': fits}
            return fx['_nonqb']

        # THE QB HALF FIRST, because C3 and A1 consume it. In the baseline
        # configuration there is no QB object to pass and the engine's own
        # defaults apply unchanged.
        qb = None
        rushing_budget = None
        rush_categories = None
        shared_pass = 'off'
        game_coupling = 'none'
        if _mode['mode'] != 'PRODUCTION_BASELINE':
            qo = _candidate_qb()
            if qo.state is not State.PASS:
                fx['_nonqb'] = {'fatal': qo}
                return fx['_nonqb']
            qb = fx.get('_qb_object')
            shared_pass = fl.get('shared_pass') or 'off'
            game_coupling = fl.get('game_coupling') or 'none'
            a1 = fx.get('_rushing_a1')
            if a1 is not None and a1.state is State.PASS:
                # A1's OWN carry level is the SC1-coupled one it partitioned.
                # Handing the engine the budget without the level it came from
                # would leave the game holding two carry vectors on different
                # draw indices.
                team_carries = dict(a1.value['team_carries'])
                # A1's `rb` CATEGORY IS THE RUNNING-BACK BUDGET. Handing the
                # engine the whole team-carry level instead would leave A1's
                # partition sitting beside a second answer to the same
                # question.
                rushing_budget = {
                    t: a1.value['carries'][(t, 'rb')] for t in teams
                    if (t, 'rb') in a1.value['carries']}
                if len(rushing_budget) != len(teams):
                    o = Outcome.fail(
                        'A1_RB_BUDGET_INCOMPLETE',
                        f'A1 returned no `rb` carry budget for '
                        f'{[t for t in teams if t not in rushing_budget]}. '
                        f'Refused rather than falling back to the team level.')
                    fx['_nonqb'] = {'fatal': o}
                    return fx['_nonqb']
                fx['_coupled_team_carries'] = team_carries
                # R4. A1'S WHOLE PARTITION, NOT JUST `rb`.
                #
                # `allocate` gives every carry exactly one owner in every
                # draw across six categories; filtering to `rb` here threw
                # five of them away and left the artifact unable to say whose
                # the other carries were. D6 measured the consequence: a frame
                # mean of 24.1% of every team's carries with no modelled owner
                # (range 0.6%-45.3%), which was never missing information --
                # it was computed and discarded at this line.
                rush_categories = dict(a1.value['carries'])

        # NO EXCEPTION MAY ESCAPE THIS CHAIN. Every stage in this pipeline
        # owes a NAMED outcome; a traceback is the one thing it may not
        # return. The engine is a large composition over real artifacts, so
        # the honest assumption is that it can raise on an input nobody
        # anticipated -- and when it does, the run must still say what
        # happened in the pipeline's own vocabulary.
        try:
            g, payload = FE.run_game(
                args.season, args.week, args.game_id, players, fits.value,
                m=m, seed=args.seed, injuries_rows=None,
                test_only=bool(getattr(args, 'dry_run', False)),
                kickoff_utc=fx.get('kickoff_utc'), run_id=run_id, qb=qb,
                shared_pass=shared_pass, game_coupling=game_coupling,
                rushing_budget=rushing_budget,
                rush_categories=rush_categories,
                team_carries_override=fx.get('_coupled_team_carries'),
                tv=_team_volume(),
                appearance_spec=_appearance_spec(fl),
                observed_before=args.written_at,
                inactive_ids=fx.get('official_inactive_ids'))
        except Exception as e:                                # noqa: BLE001
            o = Outcome.fail(
                'NONQB_ENGINE_RAISED',
                f'{type(e).__name__}: {e}'[:400],
                engine_version=getattr(FE, 'ENGINE_VERSION', None))
            fx['_nonqb'] = {'fatal': o}
            return fx['_nonqb']
        fx['_nonqb'] = {'g': g, 'payload': payload,
                        'outcomes': g.get('layer_outcomes') or {}}
        if payload:
            fx['_nonqb_payload'] = payload
            # THE LEVEL THE PARTITION CONSUMED, CARRIED TO THE SEAL.
            # `football_engine` builds `published_team_targets` for exactly
            # this and says so in its own comment -- "carrying them here is
            # what lets run_forecast seal them and publish the level the
            # partition consumed" -- and then nothing read it. So the board
            # published D1's separately drawn CONTINUOUS team_targets, which
            # nothing partitions, beside an allocation built on `targeted`.
            # Receivers exceed the published level in 51.18% of 139,800 sealed
            # C3 draws and agree in none of them.
            _pe = payload.get('pass_event') or {}
            if _pe.get('published_team_targets') and _pe.get(
                    'published_level_is') == 'targeted':
                fx['_published_team_targets'] = _pe['published_team_targets']
        # C3 IS REACHED OR IT IS NOT, AND THE ENGINE SAYS WHICH. This was
        # hard-coded as "not reached" on the QB path, which was true only
        # because the chain never ran.
        sp = g['layers'].get('shared_pass') or ''
        applied = list(fx.get('_candidate_applied') or [])
        not_reached = [c for c in (fx.get('_candidate_not_reached') or [])
                       if c != 'C3']
        if shared_pass == 'c3':
            if sp.startswith('PASS'):
                applied.append('C3')
            else:
                not_reached.append('C3')
            fx['_c3_state'] = sp
            # A REFUSED HARD INVARIANT MUST REACH THE SEAL.
            #
            # `credit_passing_line` refuses a draw in which the receiving
            # event caught more balls than the quarterbacks had
            # non-intercepted attempts -- the coupling gap C3 declares and
            # does not close. The engine records that refusal in
            # `accounting['shared_pass_credit']`, sets `halted_at` and a halt
            # reason, and then DOES NOT RETURN: the run continues and seals.
            #
            # None of those three reached board.json, forecast_artifact.json
            # or run_status.json. Measured on 60 sealed boards across the
            # week-1 slate and every arm from V1_CANDIDATE to R9_W1P_GA: zero
            # occurrences of the refusal code in any sealed file. The only
            # visible symptom was the phrase `not reached`, which reads like a
            # configuration fact and is in fact a failed hard invariant.
            #
            # So the board carried a HALF-APPLIED C3 -- targets dealt from the
            # throw process, passer line NOT credited from the receiving
            # event -- and said nothing. That is this project's named worst
            # defect class, a partial result read as success, and it is what
            # made a 1,000-draw board and an 8,000-draw board on the same arm
            # look like different candidate declarations when the only
            # difference was whether enough draws were run to reach the gap.
            #
            # This transports it. It changes NO number: it is a statement
            # about a run that already happened.
            if not sp.startswith('PASS'):
                _acc = (g.get('accounting') or {})
                _st, _, _cd = sp.partition('[')
                fx['_c3_refusal'] = {
                    'seal_contract': C3_REFUSAL_CONTRACT,
                    'state': _st or 'UNKNOWN',
                    'code': _cd.rstrip(']') or 'UNKNOWN',
                    'layer_state': sp,
                    'halted_at': g.get('halted_at'),
                    'halt_reason': (g.get('halt_reason') or '')[:600],
                    'shared_pass_credit':
                        _acc.get('shared_pass_credit'),
                    'shared_pass_credit_detail':
                        _acc.get('shared_pass_credit_detail'),
                    # THE MIXTURE, NAMED. C3's first half changes the target
                    # budget; its second half credits the passer line. A run
                    # that ran one and refused the other is neither arm.
                    'first_half_applied': bool(
                        (g.get('c3') or {}).get('target_budget_owner')),
                    'passer_line_owner':
                        (g.get('c3') or {}).get('passer_line_owner'),
                    'means': 'C3 was REACHED and a hard invariant inside it '
                             'refused. This is not the same fact as an arm '
                             'that never declared C3, and the two must never '
                             'be rendered by the same phrase.'}
        if fx.get('_r5_applied'):
            applied.append('R5')
        if fx.get('_r6_applied'):
            applied.append('R6')
        if fx.get('_r7_applied'):
            applied.append('R7')
        if fx.get('_r8_applied'):
            applied.append('R8')
        # R9 IS RECORDED FROM WHAT RAN, NOT FROM WHAT WAS ASKED FOR.
        #
        # The first R9 board rendered `components applied: A1, A3G, C0, C3,
        # R2, R5, R6, R8, SC1` -- no R9 -- while every quarterback number on
        # it came from the R9 allocator. A board that does not name the
        # mechanism that produced its headline figure cannot be audited, and
        # this project's whole claim is that the chain of evidence behind a
        # number is as trustworthy as the number.
        #
        # The flag is read back from `_qb_allocator`, which is set at the
        # allocation call site from the value actually passed, so a run that
        # requested `qb_room_v2` and silently fell back could not report R9.
        # It cannot silently fall back either -- `qb_allocation.allocate`
        # returns FAIL[QB_ALLOCATOR_UNKNOWN] on an unknown name and
        # BLOCKED[QB_ROOM_V2_NEEDS_TEAM_DROPBACKS] without the draws -- but
        # the marker is derived rather than asserted regardless.
        if fx.get('_qb_allocator') == 'qb_room_v2':
            applied.append('R9')
        fx['_candidate_applied'] = sorted(set(applied))
        fx['_candidate_not_reached'] = sorted(set(not_reached))
        return fx['_nonqb']

    # Which engine layer answers for which declared pipeline stage. The two
    # vocabularies are not identical -- the engine runs receiving and rushing
    # opportunity as separate layers where the pipeline declares one
    # `targets_carries` stage -- so the mapping is written down rather than
    # inferred from a name match.
    STAGE_LAYERS = {
        'appearance': ('appearance',),
        # `participation_frame` reports whether any modelled player had to be
        # excluded for carrying no appearance draw. It belongs to this stage
        # because it is a statement about the participation evidence, and it
        # is mapped rather than added to UNREPORTED_LAYERS because it CAN
        # fail -- a team left with nobody is a real refusal.
        'participation': ('participation', 'participation_frame'),
        # R4 adds four layers to this stage and they are mapped rather than
        # listed as unreported, because every one of them CAN fail: a
        # non-integer budget, a degenerate simplex, a category matrix that
        # does not close, and a count that is not a count are all real
        # refusals and none may reach the artifact unseen.
        'targets_carries': ('targets_carries', 'carries', 'shared_pass',
                            'rushing_budget', 'carry_other_denominator',
                            'target_counts', 'carry_counts',
                            'rush_category_ownership'),
        'conversion': ('receiving_conversion',),
        'td_layer': ('receiving_td', 'rushing_td', 'counts_are_counts',
                     'stat_contract'),
    }
    # Engine layers that no declared stage answers for. They are LISTED, not
    # ignored: a layer absent from both this set and STAGE_LAYERS is a layer
    # nobody reports, and `_nonqb_stage` refuses rather than letting it pass
    # unseen. Caught the moment it happened -- `rushing_budget` failed
    # RUSHING_BUDGET_EXCEEDS_TEAM_CARRIES, no stage was mapped to it, and the
    # run sealed anyway. A failing layer that no stage owns is exactly the
    # absence-read-as-success defect, and mapping the layers I happened to
    # think of is not a fix for it.
    UNREPORTED_LAYERS = frozenset({
        'game_coupling',             # reported via candidate_components
        'rushing_budget_owner',      # a label, not an outcome
        'rushing_conversion',        # DEFERRED by declared open decision
        'team_environment',          # its own declared stage owns this
    })

    def _assert_every_layer_is_reported(g):
        """No engine layer may go unreported. Returns an Outcome or None."""
        known = set(UNREPORTED_LAYERS)
        for names in STAGE_LAYERS.values():
            known.update(names)
        orphan = sorted(set(g.get('layers') or {}) - known)
        if orphan:
            return Outcome.fail(
                'ENGINE_LAYER_NOT_REPORTED',
                f'the engine ran layer(s) {orphan} that no declared stage '
                f'answers for, so their state would never reach the '
                f'artifact. A layer nobody reports is a layer whose failure '
                f'is invisible.', orphan=orphan)
        return None

    def _nonqb_stage(_st):
        """One declared stage's real outcome, from the engine that ran it."""
        res = _nonqb_chain()
        if 'fatal' in res:
            return res['fatal']
        unreported = _assert_every_layer_is_reported(res['g'])
        if unreported is not None:
            return unreported
        outs = res['outcomes']
        names = STAGE_LAYERS[_st]
        got = [(n, outs[n]) for n in names if n in outs]
        if not got:
            # THE ENGINE HALTED BEFORE THIS STAGE, AND THE CODE SAYS WHERE.
            #
            # A generic UPSTREAM_LAYER_NOT_EXECUTED is only marginally better
            # than the STAGE_DECLARED_UNIMPLEMENTED label this pipeline was
            # already caught using: both tell an operator that nothing ran and
            # neither tells them what to go and fix. The halting layer's name
            # and its own refusal code travel with the refusal instead.
            g = res['g']
            at = g.get('halted_at') or 'an_earlier_layer'
            up = outs.get(at)
            return Outcome.not_applicable(
                f'BLOCKED_UPSTREAM_{at.upper()}',
                f'{_st} was not reached: the engine halted at {at}'
                + (f' with {up.code}' if up is not None else '')
                + (f' -- {g.get("halt_reason")}' if g.get('halt_reason')
                   else ''),
                halted_at=at,
                upstream_code=(up.code if up is not None else None))
        bad = [(n, o) for n, o in got if o.state is not State.PASS]
        if bad:
            # The WORST layer answers for the stage, and it answers in its own
            # words. Collapsing two layers into one invented code would lose
            # which of them refused.
            n, o = bad[0]
            return o
        return Outcome.ok(
            f'{_st.upper()}_OK',
            value={n: (o.evidence.get('n_players') or o.value)
                   for n, o in got},
            layers={n: f'{o.state.value}[{o.code}]' for n, o in got},
            spec_versions={n: o.evidence.get('spec_version') for n, o in got},
            test_only=any(bool(o.evidence.get('test_only')) for _n, o in got),
            **_governance_facts(got))


    for stage, key, spec in (
            ('feature_build', 'features', 'prior-only, ordinal prefix cut'),
            ('team_environment', 'team_env', TV.SPEC_VERSION),
            ('appearance', 'appearance', 'P3 appearance'),
            ('participation', 'participation',
             'Stage2 ewma_hl2; governance INFORMATION_CONSTRAINED'),
            ('targets_carries', 'targets_carries',
             'P4C system C; governance DATA_BLOCKED'),
            ('conversion', 'conversion',
             'RC1 baseline; SIGNAL_WEAK; governance HOLD_CHARACTERIZED '
             '+ CALIBRATION_DEFECT'),
            ('td_layer', 'td',
             'TD2 pooled positional control; governance HOLD_TENTATIVE'),
            ('qb_layer', 'qb', QBV1.SPEC_VERSION)):
        def _model(_k=key, _s=spec, _st=stage):
            # ARTIFACT AND HASH CHECKS COME FIRST, ALWAYS. Running the model
            # before verifying its artifact would let a hash mismatch produce a
            # forecast and only then be noticed -- and in an earlier draft of
            # this file the QB branch sat above these and did exactly that.
            if fx.get(f'{_k}_missing'):
                return RF.refuse('MODEL_ARTIFACT_MISSING', _st,
                                 f'{_k} model artifact is absent', run_id)
            if fx.get(f'{_k}_hash_mismatch'):
                return RF.refuse('MODEL_HASH_MISMATCH', _st,
                                 f'{_k} artifact hash differs', run_id)
            if fx.get(f'{_k}_not_implemented'):
                return RF.refuse('STAGE_NOT_IMPLEMENTED', _st,
                                 f'{_k} has no production model; a named '
                                 f'refusal is returned rather than a '
                                 f'fabricated forecast', run_id)
            if _st == 'qb_layer' and (fx.get('qb_rows') is not None
                                      or fx.get('qb_slate')):
                # REAL MODEL LOGIC, not a dummy dictionary.
                #
                # DERIVED ARTIFACTS FIRST. `qb2_lib.load()` reads
                # panel_enriched.pkl through p4c_build, and that artifact is
                # deliberately NOT committed -- it is regenerated from the
                # leaves under nfl/research/inputs. In a fresh checkout it is
                # simply absent, and the loader raised FileNotFoundError, which
                # the pipeline recorded as STAGE_RAISED. The whole 2026 week 1
                # slate refused on a Python traceback rather than a named
                # cause, and a traceback is not a refusal reason.
                #
                # `football_engine.qb_slate` already gated on this; the
                # production entrypoint did not. Same call, same order, so the
                # QB layer cannot depend on a copy someone happened to leave in
                # the research tree either.
                da = DERIVED.artifacts()
                if da.state is not State.PASS:
                    return RF.refuse('MODEL_ARTIFACT_MISSING', _st,
                                     f'{da.code}: {da.detail}', run_id)
                if _mode['candidate']:
                    o = _candidate_qb()
                    if o.state is not State.PASS:
                        return o
                    return o
                fh = QBV1.artifact_hash()
                if fh.state is not State.PASS:
                    return RF.refuse('MODEL_ARTIFACT_MISSING', _st,
                                     fh.detail, run_id)
                if fx.get('qb_rows') is None:
                    qbp = [q for q in fx.get('players', [])
                           if q.get('position') == 'QB' and q.get('gsis_id')]
                    sl = (QBV1.slate_prospective(args.season, args.week, qbp)
                          if fx['qb_slate'].get('prospective')
                          else QBV1.slate(args.season, args.week,
                                          fx['qb_slate'].get('game_ids')))
                    if sl.state is not State.PASS:
                        return sl
                    fx['qb_rows'], fx['qb_allrows'] = sl.value
                o = QBV1.forecast(fx['qb_rows'], args.season,
                                  fx.get('qb_allrows', fx['qb_rows']),
                                  seed=args.seed, m=fx.get('qb_draws', 200))
                if o.state is not State.PASS:
                    return o
                # B14. THE VERDICT IS KEPT AS AN OUTCOME, NOT A STRING.
                # These three already refused here, which is right and stays.
                # What was missing is that the artifact carried no record of
                # them at all, so a sealed artifact could not be interrogated
                # about the invariants it claims to satisfy -- only about the
                # ones that happened to stop the run.
                _inv = fx.setdefault('_inv', {})
                # A DECLARED INVARIANT THAT THIS CONFIGURATION CANNOT EVALUATE
                # STILL GETS A VERDICT. Single-owner rushing is an A1 property
                # and A1 is a candidate component, so the baseline has nothing
                # to evaluate -- but declaring it HARD and then saying nothing
                # made every baseline run refuse with INVARIANT_VERDICT_MISSING.
                # "Not applicable in this configuration, and here is why" is an
                # answer; silence is not.
                _inv['rushing_single_owner'] = Outcome.not_applicable(
                    'RUSHING_SINGLE_OWNER_NOT_IN_THIS_CONFIGURATION',
                    'A1 is a V1 candidate component and this run is '
                    'PRODUCTION_BASELINE, which has no single-owner rushing '
                    'allocation to check. Recorded rather than left silent.')
                _inv['scramble_carry_coherence'] = Outcome.not_applicable(
                    'SCRAMBLE_CARRY_COHERENCE_NOT_IN_THIS_CONFIGURATION',
                    'SC1 is a V1 candidate component and this run is '
                    'PRODUCTION_BASELINE, which forms no rush-play budget '
                    'from carries and scrambles. Recorded, not left silent.')
                ident = QBV1.identity_check(o.value)
                _inv['qb_dropback_identity'] = ident
                if ident.state is not State.PASS:
                    return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', _st,
                                     ident.detail, run_id)
                acct = QBACC.reconcile_draws(o.value)
                _inv['qb_per_draw_accounting'] = acct
                if acct.state is not State.PASS:
                    return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', _st,
                                     f'{acct.code}: {acct.detail}', run_id)
                team = QBACC.reconcile_team(
                    o.value, fx['qb_rows'],
                    team_rush_draws=fx.get('team_rush_draws'),
                    team_rushes_realised=fx.get('team_rushes_realised'),
                    team_dropback_draws=_qb_dropback_budgets(),
                    # `_mode` is what this scope holds; `fl` is bound in the
                    # other stage runner and reaching for it here raised
                    # NameError inside the qb_layer, which the pipeline
                    # correctly recorded as STAGE_RAISED and the suite caught.
                    integer_level=bool(
                        (_mode.get('flags') or {}).get('r2')))
                _inv['qb_team_accounting'] = team
                _inv['qb_inactive_owns_nothing'] = (
                    QBACC.assert_inactive_qbs_own_nothing(
                        o.value, fx['qb_rows'],
                        fx.get('official_inactive_ids')))
                if _inv['qb_inactive_owns_nothing'].state is State.FAIL:
                    return RF.refuse(
                        'INCOMPLETE_PLAYER_ACCOUNTING', _st,
                        f"{_inv['qb_inactive_owns_nothing'].code}: "
                        f"{_inv['qb_inactive_owns_nothing'].detail}", run_id)
                fx['_qb_team_warnings'] = list(team.evidence.get('warnings')
                                               or [])
                if team.state is not State.PASS:
                    return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', _st,
                                     f'{team.code}: {team.detail}', run_id)
                fx['_qb_draws_out'] = o.value
                fx['_qb_accounting'] = {'per_draw': acct.value,
                                        'team': team.value}
                return Outcome.ok(
                    'QB_LAYER_OK', value=o.value,
                    draw_generation_seconds=o.evidence.get(
                        'draw_generation_seconds'),
                    qb_frame_sha256=fh.value,
                    n_qb_games=o.evidence.get('n_qb_games'),
                    n_draws=o.evidence.get('n_draws'),
                    draw_cells=o.evidence.get('draw_cells'),
                    warnings=[f'known limitation: {k}'
                              for k in QBV1.KNOWN_LIMITATIONS]
                    + list(team.evidence.get('warnings') or []),
                    warnings_detail=(
                        [{'layer': 'qb_v1',
                          'warning': f'known limitation: {k}'}
                         for k in QBV1.KNOWN_LIMITATIONS]
                        + [{'layer': 'qb_team_accounting', 'warning': w}
                           for w in (team.evidence.get('warnings') or [])]))
            # A STAGE MAY NOT CLAIM AN ACCEPTED SPEC AND PRODUCE NOTHING.
            # Six stages carried strings like 'P4C system C ACCEPTED' while
            # returning {} and reporting PASS. The accepted research baseline
            # exists; a PRODUCTION IMPLEMENTATION of it does not, and the
            # pipeline said nothing about the difference.
            if _st == 'team_environment' and fx.get('team_volume'):
                o = _team_volume()
                if o.state is not State.PASS:
                    return o
                return Outcome.ok(
                    'TEAM_ENVIRONMENT_OK', value={'n': len(o.value)},
                    implemented=True, spec_version=TV.SPEC_VERSION,
                    n_metrics=len(TV.METRICS),
                    warnings=[f'known limitation: {k}'
                              for k in TV.KNOWN_LIMITATIONS],
                    warnings_detail=[{'layer': 'team_volume',
                                      'warning': f'known limitation: {k}'}
                                     for k in TV.KNOWN_LIMITATIONS])
            _v = fx.get(_k)
            if not _v and _st in NONQB_CHAIN:
                # THE NON-QB CHAIN IS IMPLEMENTED. Reporting it as
                # "no production implementation" was false and it cost the
                # artifact its true refusal reason: `slate_rehearsal` calls
                # these same layers and gets
                # DEFERRED[INJURIES_2026_PUBLISHED_BUT_INSUFFICIENT] with the
                # cascade named beneath it, while the production entrypoint
                # said "unimplemented" and recorded PASS. A stage blocked on an
                # unusable input is not a stage that was never built, and an
                # operator reading the artifact could not tell which it was.
                #
                # Calling the real layer here means the artifact carries the
                # actual cause today, and that the feed arriving is an input
                # unblock rather than a code change.
                o = _nonqb_stage(_st)
                if o is not None:
                    if o.state is State.PASS:
                        return o
                    # A NON-QB LAYER THAT CANNOT RUN DOES NOT REFUSE THE GAME.
                    # It is a completeness dimension, not a required input:
                    # the accepted design seals the QB forecast and declares
                    # what is missing (`completeness`, `absent_layers`). That
                    # policy is preserved here and only the REASON improves --
                    # wiring the real layer in first made a deferred injury
                    # feed refuse all 16 games, which threw away a valid QB
                    # forecast over a layer that had never been required.
                    #
                    # No probability is emitted either way, so nothing is
                    # fabricated. The layer's OWN code and detail are kept, so
                    # the artifact says INJURY_REPORT_NOT_YET_FILED rather than
                    # the false 'no production implementation'. Required
                    # stages -- capture, identity, team environment, QB,
                    # reconciliation, draws, sealing -- keep halting.
                    return Outcome.not_applicable(
                        o.code, f'{_st}: {o.detail}'[:400],
                        implemented=True, layer=_k, blocked_layer=True,
                        layer_state=o.state.value,
                        # A LAYER THAT COULD NOT RUN STILL SAID THINGS.
                        # Rewrapping its Outcome here dropped whatever
                        # governance and warnings it had already declared, so
                        # the refusing case lost exactly what the passing case
                        # lost. Carried through unchanged, same as above.
                        **{k: v for k, v in (o.evidence or {}).items()
                           if k in ('warnings', 'warnings_detail',
                                    'governance', 'spec_version',
                                    'spec_versions') and v})

            if not _v:
                # PASS ANSWERED A DIFFERENT QUESTION THAN IT WAS READ AS.
                #
                # This returned Outcome.ok, so the run summary printed
                # `feature_build PASS STAGE_DECLARED_UNIMPLEMENTED`. PASS here
                # meant "the control flow executed and the gap was declared
                # correctly". Every reader takes it to mean "this stage
                # produced a feature". Those are different questions and the
                # word answered the wrong one.
                #
                # DEFERRED is this pipeline's existing vocabulary for exactly
                # this -- declared debt, carried into the artifact as OWED and
                # never as passed. Three separate facts are now reported
                # instead of one overloaded state: the control flow ran
                # (executed), the feature does not exist (implemented), and it
                # is therefore not product-ready (product_ready).
                return Outcome.deferred(
                    'STAGE_DECLARED_UNIMPLEMENTED',
                    detail=f'{_st}: the accepted research baseline {_s!r} has '
                           f'no production implementation. Declared as debt '
                           f'rather than reported as a successful forecast.',
                    value={}, executed=True, implemented=False,
                    product_ready=False, owed=f'{_st}:{_s}', layer=_k)
            return Outcome.ok(f'{_st.upper()}_OK', value=_v, implemented=True)
        p.run_stage(stage, _model, declared_inputs=['h_history', 'q_pos_mean'],
                    spec_version=spec)

    # --- 11. joint reconciliation ---------------------------------------
    def _joint():
        if fx.get('joint_fails'):
            return RF.refuse('JOINT_RECONCILIATION_FAILURE',
                             'joint_reconciliation',
                             'team totals could not be reconciled', run_id)
        if fx.get('accounting_fails'):
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING',
                             'joint_reconciliation',
                             'team and player totals do not reconcile', run_id)
        j = dict(fx.get('joint', {}))
        if fx.get('_qb_draws_out') is not None:
            x = QBACC.reconcile_cross_layer(
                fx['_qb_draws_out'], receiving=fx.get('receiving_yard_draws'),
                receiving_td=fx.get('receiving_td_draws'))
            if x.state is State.FAIL:
                return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING',
                                 'joint_reconciliation',
                                 f'{x.code}: {x.detail}', run_id)
            # DEFERRED is carried into the artifact as OWED, never as passed.
            fx.setdefault('_inv', {})['qb_cross_layer_reconciliation'] = x
            j['qb_cross_layer'] = {'state': x.state.value, 'code': x.code,
                                   'owed': x.evidence.get('owed') if x.state is State.DEFERRED
                                   else None}
            j['qb_accounting'] = fx.get('_qb_accounting')
        return Outcome.ok('JOINT_RECONCILED', value=j)
    p.run_stage('joint_reconciliation', _joint,
                declared_inputs=['player_draws', 'team_volume'],
                spec_version='minimum-viable production coupling')

    # --- 12. player draws / 13. scoring / 14. sealing --------------------
    def _draws():
        """Assemble every layer's draws into ONE joint, replayable draw set.

        Previously this returned fx['draws'] -- a fixture key nothing ever set
        -- so the stage passed with {} while the QB layer's real draws were
        computed and thrown away. The rehearsal sealed 16 artifacts containing
        zero forecasts and reported PASS on all of them.

        B13. It then reduced every metric to mean/p10/p50/p90 and threw the
        draws away a second time. Four quantiles cannot produce CRPS, a log
        score, a PIT value, coverage at an unstored level, a tail probability
        or ANY dependence diagnostic -- the last of those is not recoverable by
        storing more quantiles, because a per-metric marginal summary has
        already discarded which draw went with which.

        So the draws themselves are written to a sidecar container on a shared
        draw index and referenced from the artifact by hash, and the quantile
        view is KEPT alongside as the convenient view it always was. The two
        are then checked against each other, so they cannot describe different
        runs.
        """
        inv = fx.setdefault('_inv', {})

        def _fail(o):
            """Attribute a draw refusal to the invariant it is evidence about."""
            inv[DRAW_CODE_INVARIANT.get(o.code, DRAW_CODE_INVARIANT_DEFAULT)] = o
            return o

        import numpy as _np
        ds = DA.DrawSet(run_id=run_id, game_id=args.game_id, seed=args.seed,
                        seed_protocol=f'per-row seed {args.seed}')
        # P2 -- THE MATRICES THAT ARE ACTUALLY SEALED.
        #
        # The coherence checks may not run inside the engine. The engine reads
        # the SC1-coupled carry vector and this stage seals D1's raw one, so
        # an engine-side carry check attests to a vector nobody publishes --
        # which is how `SC1_COHERENT` reads PASS in nine sealed runs whose
        # published scramble total exceeds their published carry total.
        #
        # `_p2` therefore collects exactly what is handed to `add_layer`, by
        # the same `<layer>/<key>` names the checks address, and `_p2_rows`
        # collects each team's ROW INDICES per layer. Row identity is resolved
        # here and never joined positionally across layers.
        _p2, _p2_rows = {}, {}

        def _p2_add(layer, row_ids, mats, team_of, scalar_row=False):
            """Record one layer's published matrices and its team row map.

            `scalar_row` is the team_volume shape and is passed explicitly,
            not inferred from the layer name. A team-keyed matrix has ONE row
            per team, and `draw_coherence.carry_containment` indexes it as a
            scalar; handing it a one-element list raised TypeError inside the
            check and refused the whole draws stage. The two shapes are the
            caller's to get right, so they are declared here.
            """
            for k, v in mats.items():
                _p2[f'{layer}/{k}'] = v
            for i, rid in enumerate(row_ids):
                t = team_of(rid)
                if not t:
                    continue
                if scalar_row:
                    _p2_rows.setdefault(t, {})[layer] = i
                else:
                    _p2_rows.setdefault(t, {}).setdefault(layer, []).append(i)

        # A KEY WHOSE VALUE IS None IS NOT AN ANSWER, AND IT BLOCKS THE ONE
        # THAT IS. This comprehension wrote `gsis_id -> None` for any player
        # the roster feed could not place, and the `setdefault` below then saw
        # the key already present and declined to fill it from `qb_rows` --
        # which DOES carry the club, because the quarterback frame is built
        # from the QB panel rather than from the roster feed.
        #
        # The consequence was not a missing team on a board nobody reads: it
        # was `rushing_total` refusing with DRAW_LAYER_ROWS_WITHOUT_A_TEAM for
        # 12 of 12 rows on a fixture whose quarterbacks all had clubs, which
        # stopped the pipeline at `player_draws` and took two governance tests
        # down with it. Only a REAL team is recorded, so the fallbacks below
        # can do their job.
        _team_of_player = {q['gsis_id']: q['team']
                           for q in (fx.get('players') or [])
                           if q.get('gsis_id') and q.get('team')}
        for _r in (fx.get('qb_rows') or []):
            if _r.get('gsis_id') and _r.get('team'):
                _team_of_player.setdefault(_r['gsis_id'], _r['team'])

        produced = {}
        D = fx.get('_qb_draws_out')
        rows = fx.get('qb_rows') or []
        if D is not None and rows:
            o = ds.add_layer(
                'qb', [r['gsis_id'] for r in rows],
                {f: _np.asarray(D[f]) for f in QBV1.FIELDS},
                QBV1.SPEC_VERSION,
                'numpy default_rng([seed, ord, gsis_id]) -- one stream per '
                'row; columns are aligned, rows are independent',
                row_teams={r['gsis_id']: r.get('team') for r in rows})
            if o.state is not State.PASS:
                return _fail(o)
            produced['qb'] = len(rows)
            _p2_add('qb', [r['gsis_id'] for r in rows],
                    {f: _np.asarray(D[f]) for f in QBV1.FIELDS},
                    lambda pid: _team_of_player.get(pid))
        # THE NON-QB CHAIN'S DRAWS. Without this the chain could execute,
        # pass every accounting check, and have its output thrown away at the
        # sidecar -- which is the same defect B13 was written for, one layer
        # further along. `absent_layers` in the artifact would then say
        # `receiving` and `rushing` were absent on a run where they ran.
        pay = fx.get('_nonqb_payload')
        if pay:
            idx = pay['index']
            rec_ids = idx['recv_ids']
            if rec_ids:
                o = ds.add_layer(
                    'receiving', rec_ids,
                    {'targets': _np.asarray(pay['draws']['targets']),
                     'receptions': _np.asarray(pay['draws']['receptions']),
                     'receiving_yards':
                         _np.asarray(pay['draws']['receiving_yards']),
                     'receiving_td': _np.asarray(
                         pay['draws']['receiving_td'])},
                    'nfl-nonqb-receiving-1',
                    'P4C simplex allocation and RC1 conversion on the shared '
                    'game draw index',
                    row_teams={g: _team_of_player.get(g) for g in rec_ids})
                if o.state is not State.PASS:
                    return _fail(o)
                produced['receiving'] = len(rec_ids)
                _p2_add('receiving', rec_ids,
                        {'targets': _np.asarray(pay['draws']['targets']),
                         'receptions': _np.asarray(
                             pay['draws']['receptions']),
                         'receiving_yards': _np.asarray(
                             pay['draws']['receiving_yards']),
                         'receiving_td': _np.asarray(
                             pay['draws']['receiving_td'])},
                        lambda pid: _team_of_player.get(pid))
            rb_ids = idx['rb_ids']
            if rb_ids:
                # RUSHING YARDS SEAL WITH THE CARRIES THAT PRODUCED THEM.
                # The conversion consumed this exact carry matrix, so the two
                # metrics share rows and draw index by construction. Sealing
                # them in one layer is what stops a later reader pairing a
                # yard total with a carry count from a different world.
                _rushmats = {
                    'carries': _np.asarray(pay['draws']['carries']),
                    'rushing_td': _np.asarray(pay['draws']['rush_td'])}
                _ryd = pay['draws'].get('rushing_yards')
                if _ryd is not None:
                    _rushmats['rushing_yards'] = _np.asarray(_ryd)
                o = ds.add_layer(
                    'rushing', rb_ids, _rushmats,
                    'nfl-nonqb-rushing-1',
                    'P4C simplex allocation over the A1 running-back budget '
                    'on the shared game draw index; rushing_yards drawn per '
                    'carry by the adjudicated emp_tilt system-A control',
                    row_teams={g: _team_of_player.get(g) for g in rb_ids})
                if o.state is not State.PASS:
                    return _fail(o)
                produced['rushing'] = len(rb_ids)
                _p2_add('rushing', rb_ids, _rushmats,
                        lambda pid: _team_of_player.get(pid))
            # R4. THE RUSH CATEGORY MATRIX, ROW AXIS = TEAM.
            #
            # D6's highest-value recommendation, and its wording: "sealing the
            # category matrix makes the entire rush partition auditable from a
            # sealed board, and would let the 24.1% residual be attributed
            # instead of merely measured." One metric per A1 category plus the
            # unmodelled-back pool the player deal names, so a reader of the
            # npz can walk team carries -> category -> player -> pool without
            # re-running the allocator or trusting a summary.
            rc = pay.get('rush_category')
            if rc:
                rc_teams = sorted(rc)
                mats = {c: _np.stack([_np.asarray(rc[t][c], float)
                                      for t in rc_teams])
                        for c in sorted(next(iter(rc.values())))}
                o = ds.add_layer(
                    'rush_category', rc_teams, mats,
                    'nfl-rushing-a1-category-1',
                    'rushing_a1: ONE multinomial per team per draw over the '
                    'rush-play budget; every carry has exactly one owner',
                    row_axis='team')
                if o.state is not State.PASS:
                    return _fail(o)
                produced['rush_category'] = len(rc_teams)
                _p2_add('rush_category', rc_teams, mats, lambda t: t,
                        scalar_row=True)
            # THE UNMODELLED-BACK POOL IS A SEPARATE LAYER ON ITS OWN ROWS.
            #
            # It is the part of the `rb` CATEGORY that the player deal gave to
            # backs outside the modelled set, so it exists only for a team
            # whose appearance layer ran -- tonight, Kansas City and not
            # Denver. Carrying it as a column of `rush_category` would force a
            # row for every team in that matrix and a deferred team has no
            # honest value to put there; a zero would read as "no unmodelled
            # backs" when the truth is "no player split was made".
            rcp = pay.get('rush_category_other')
            if rcp:
                rcp_teams = sorted(rcp)
                mats = {'unmodelled_back_pool': _np.stack(
                    [_np.asarray(rcp[t], float) for t in rcp_teams])}
                o = ds.add_layer(
                    'rush_player_pool', rcp_teams, mats,
                    'nfl-rushing-a1-category-1',
                    'the share of the A1 `rb` category dealt to backs outside '
                    'the modelled set, on the shared game draw index',
                    row_axis='team')
                if o.state is not State.PASS:
                    return _fail(o)
                produced['rush_player_pool'] = len(rcp_teams)
                _p2_add('rush_player_pool', rcp_teams, mats, lambda t: t,
                        scalar_row=True)
        tv = fx.get('_team_volume')
        if tv:
            teams = sorted({t for (_m, t) in tv})
            # R11. SEAL THE CARRY VECTOR THE GAME CONSUMED.
            #
            # D1 draws a CONTINUOUS team-carry level; SC1 permutes which draw
            # index receives which value and A1 integerises it, and it is that
            # vector the six categories and the running-back deal partition.
            # Sealing D1's raw draw beside them published a denominator the
            # game never used, which is why a containment breach could not be
            # attributed between a carry with two owners and a wrong vector --
            # `draw_coherence.team_qb_rush_opportunity_within_team_carries`
            # says so in its own `why_not_hard`. The substitution is a
            # PERMUTATION composed with A1's declared round-half-even, so the
            # carry marginal is unchanged element for element; no value is
            # clipped and no draw is dropped. Only the R11 composition sets
            # this key, so every other configuration seals exactly what it
            # sealed before.
            _pub = fx.get('_published_team_carries') or {}
            _tvc = dict(tv)
            for _t, _v in _pub.items():
                if ('team_carries', _t) in _tvc:
                    _tvc[('team_carries', _t)] = _np.asarray(_v, float)
            # THE SAME CORRECTION ON THE RECEIVING SIDE, and it is a
            # PUBLICATION fix rather than an allocation one. The partition is
            # already sound -- targets never exceed attempts in any draw -- so
            # renormalising it would break something that works. What was
            # wrong is that the sealed vector was not the vector partitioned.
            # Gated on the candidate flag, so every frozen arm seals exactly
            # what it sealed before.
            if (_mode['flags'] or {}).get('publish_partitioned_team_targets'):
                _pt = fx.get('_published_team_targets') or {}
                for _t, _v in _pt.items():
                    if ('team_targets', _t) in _tvc:
                        _tvc[('team_targets', _t)] = _np.asarray(_v, float)
                fx['_team_targets_published_level'] = (
                    'targeted (the level the multinomial dealt from)'
                    if _pt else 'D1 (no pass event composed)')
            tv = _tvc
            mats = {m: _np.stack([_np.asarray(tv[(m, t)], float)
                                  for t in teams])
                    for m in TV.METRICS if all((m, t) in tv for t in teams)}
            if mats:
                o = ds.add_layer(
                    'team_volume', teams, mats, TV.SPEC_VERSION,
                    'nfl.production.seeds declared streams, per metric',
                    row_axis='team')
                if o.state is not State.PASS:
                    return _fail(o)
                produced['team_volume'] = len(teams)
                _p2_add('team_volume', teams, mats, lambda t: t,
                        scalar_row=True)
                # THE BINDING. `teams` here is the matrix row order; the
                # artifact's `team_ids` is a different order of the same set.
                # Record the map so no consumer has to infer it, and refuse if
                # the two ever stop describing the same teams -- a matrix that
                # covers different teams from the artifact is not a reordering,
                # it is a different run.
                fx['_team_draw_row_index'] = {t: i for i, t in enumerate(teams)}
                _declared = set(fx.get('team_ids') or [])
                if _declared and _declared != set(teams):
                    return _fail(Outcome.fail(
                        'TEAM_DRAW_ROWS_DISAGREE_WITH_TEAM_IDS',
                        f'the team_volume draw matrix covers {sorted(teams)} '
                        f'while the artifact declares {sorted(_declared)}. '
                        f'A row order may differ; the SET may not.',
                        matrix_teams=sorted(teams),
                        declared_teams=sorted(_declared)))

        # ---- THE RUSHING MASS THAT HAD NO PLAYER ---------------------
        #
        # A1 loses no carry -- every one lands in exactly one category. What
        # it does not do is say WHO. kneel, wr and te reached the board as a
        # team number with nobody on it: 2.87 of Buffalo's 30.08 carries and
        # 1.75 of Detroit's 29.21. The kneels are the ones that bite, because
        # a kneel is an official rush attempt that loses a yard, so hiding
        # them overstates the rushing line of every quarterback whose team is
        # ahead.
        #
        # THIS CHANGES WHAT THE BOARD CLOSES OVER, so it is gated on its own
        # candidate identity and every frozen arm seals exactly what it
        # sealed before. fringe and the unmodelled-back pool are NOT
        # allocated: their owners are punters, defensive backs and players
        # with no position in any source held, and inventing a name for them
        # would be worse than the gap.
        _gadget = {'allocated': {}, 'not_allocated': dict(GADGET.NOT_ALLOCATED)}
        if ds.arrays and not fx.get('distributions') \
                and (_mode['flags'] or {}).get('allocate_gadget_rush'):
            _gord = int(args.season) * 100 + int(args.week)
            _gfit = GADGET.fit(_gord)
            if _gfit.state is not State.PASS:
                _gadget['fit'] = f'{_gfit.state.value}[{_gfit.code}]'
            else:
                _gdoc = _gfit.value
                _g_rows, _g_mats, _g_meta = [], {}, {}
                _cat_rows = ds.layers.get('rush_category', {}).get(
                    'row_ids') or []
                for _t in _cat_rows:
                    _ti = _cat_rows.index(_t)
                    _mates = [g for g, tt in _team_of_player.items()
                              if tt == _t]
                    for _cat in GADGET.CATEGORIES:
                        _mat = _p2.get(f'rush_category/{_cat}')
                        if _mat is None:
                            continue
                        _al = GADGET.allocate(
                            _gdoc, _t, _cat, _np.asarray(_mat)[_ti],
                            _mates, int(args.seed), tag=f'{_gord}:{_t}')
                        if _al.state is State.FAIL:
                            return _fail(_al)
                        if _al.state is not State.PASS:
                            _gadget['allocated'][f'{_t}/{_cat}'] = \
                                f'{_al.state.value}[{_al.code}]'
                            continue
                        for _j, _pid in enumerate(_al.value['row_ids']):
                            _g_meta.setdefault(_pid, {})[_cat] = _t
                            _g_mats.setdefault(_cat, {})[_pid] = \
                                _al.value['counts'][_j]
                        _gadget['allocated'][f'{_t}/{_cat}'] = {
                            k: v for k, v in _al.as_dict()['evidence'].items()
                            if k != 'value'}
                    # KNEELS TO THE QUARTERBACK WHO THREW MOST IN THAT DRAW.
                    _kn = _p2.get('rush_category/kneel')
                    _qrows = (_p2_rows.get(_t) or {}).get('qb') or []
                    if _kn is not None and _qrows and 'qb/db' in _p2:
                        _qids = [(ds.layers['qb']['row_ids'])[_r]
                                 for _r in _qrows]
                        _kal = GADGET.kneels_to_primary_passer(
                            _np.asarray(_kn)[_ti],
                            _np.asarray(_p2['qb/db'])[list(_qrows)], _qids)
                        if _kal.state is State.FAIL:
                            return _fail(_kal)
                        if _kal.state is State.PASS:
                            for _j, _pid in enumerate(_kal.value['row_ids']):
                                _g_mats.setdefault('kneel', {})[_pid] = \
                                    _kal.value['counts'][_j]
                        _gadget['allocated'][f'{_t}/kneel'] = {
                            k: v for k, v in _kal.as_dict()['evidence'].items()
                            if k != 'value'}
                # NAMED CARRIES MUST OWN NAMED YARDS. Allocating the carry
                # and leaving the yard behind was the gap this closes: a
                # kneel LOSES 1.09 yards and a jet sweep gains 5.54 against
                # an RB pool mean of 4.29, so routing either through the RB
                # pool would have been worse than the gap it filled.
                if _g_mats:
                    from nfl.production.nonqb import rushing_conversion as RCV
                    _gp = RCV.gadget_pools(_gord)
                    if _gp.state is not State.PASS:
                        return _fail(_gp)
                    _gpv = _gp.value
                    for _cat in list(_g_mats):
                        if _cat not in RCV.GADGET_STRATA:
                            continue
                        for _pid, _cnt in list(_g_mats[_cat].items()):
                            _g_mats.setdefault(_cat + '_yards', {})[_pid] = \
                                RCV.gadget_yards_for(
                                    _cnt, _cat, _gpv, int(args.seed),
                                    f'{_gord}:{_pid}')
                    _gadget['yard_strata'] = _gp.as_dict()['evidence'][
                        'provenance']['strata']
                if _g_mats:
                    # ONE LAYER, ONE ROW PER PLAYER, ONE COLUMN PER CATEGORY.
                    # A player who takes only wr carries carries a zero row
                    # for kneel, which is a real zero -- he did not kneel --
                    # rather than an absence.
                    _g_rows = sorted({p for c in _g_mats for p in _g_mats[c]})
                    _mats2 = {
                        c: _np.stack([_np.asarray(
                            _g_mats[c].get(p, _np.zeros(int(ds.n_draws))),
                            float) for p in _g_rows])
                        for c in sorted(_g_mats)}
                    o = ds.add_layer(
                        'gadget_rush', _g_rows, _mats2, GADGET.SPEC_VERSION,
                        'multinomial over the club\'s named players at the '
                        'position, weights = own prior carries + fitted '
                        'alpha; kneels by per-draw dropback argmax',
                        row_teams={g: _team_of_player.get(g)
                                   for g in _g_rows})
                    if o.state is not State.PASS:
                        return _fail(o)
                    produced['gadget_rush'] = len(_g_rows)
                    _p2_add('gadget_rush', _g_rows, _mats2,
                            lambda g: _team_of_player.get(g))
                    # THE ROWS ARE NAMED HERE, and three of them are why.
                    # The allocation deals to the complete lawful participant
                    # universe, which is WIDER than the displayed board: on
                    # DET-BUF, three receivers took gadget carries while
                    # appearing on no display row. That is correct football --
                    # the board shows QB/RB/WR1-3/TE/K and the simulator must
                    # not be limited to it -- but it means board.json cannot
                    # name every gadget row, and reading team from there
                    # returned None and made the conservation check look
                    # broken. The identity is published with the layer.
                    _pmeta = {q['gsis_id']: q for q in
                              (fx.get('players') or []) if q.get('gsis_id')}
                    _pmeta.update({r['gsis_id']: r for r in
                                   (fx.get('qb_rows') or [])
                                   if r.get('gsis_id')})
                    # NAMES COME FROM THE SAME RESOLVER THE BOARD USES, and
                    # an unresolved id stays the id. `nfl.product.names` is
                    # display-only by contract -- no projection reads it --
                    # and inventing a name is worse than printing an id.
                    try:
                        _nm = NAMES.lookup(args.written_at) or {}
                    except Exception:                        # noqa: BLE001
                        _nm = {}
                    _gadget['rows'] = {
                        g: {'team': _team_of_player.get(g),
                            'name': _nm.get(g) or (_pmeta.get(g) or {}).get(
                                'name') or g,
                            'name_resolved': bool(_nm.get(g)),
                            'position': (_pmeta.get(g) or {}).get('position')}
                        for g in _g_rows}
        fx['_gadget_rush'] = _gadget

        # ---- KICKING AND DRAFTKINGS SCORING, INSIDE THE SEAL --------
        #
        # THESE USED TO BE ASSEMBLED AFTER THE SEAL, and that was the defect.
        # A script read the sealed npz, drew kicks from it and scored points,
        # and the result was a board nobody could reproduce from the artifact:
        # a second product with no run identity, no provenance bundle and no
        # publication state, whose numbers happened to agree with the sealed
        # ones because the same process had just made both. Every kick and
        # every point now originates inside this stage, on this run's draw
        # index, and seals with everything else.
        #
        # THE COUPLING IS THE REASON, not tidiness. A kicker's opportunity is
        # conditioned on his own offense's touchdowns DRAW BY DRAW: the worlds
        # where Detroit scores four times are the worlds where its kicker
        # attempts four extra points. Scoring that outside the seal would have
        # meant a reader could pair a kicking line with a different world's
        # offense and nothing would have caught it.
        _kick_notes = {}
        if ds.arrays and not fx.get('distributions'):
            _ord = int(args.season) * 100 + int(args.week)
            _kfit = KICK.fit(_ord)
            if _kfit.state is not State.PASS:
                # A refusal is RECORDED, not swallowed and not fatal. A run
                # whose passing and rushing are sound should not lose them
                # because the kicking corpus is missing.
                _kick_notes['fit'] = f'{_kfit.state.value}[{_kfit.code}]'
            else:
                _kdoc = _kfit.value
                _k_rows, _k_mats, _k_meta = [], {}, {}
                for _t in sorted(_p2_rows):
                    _rk = KICK.resolve_kicker(_kdoc, _t, args.season,
                                              args.week)
                    if _rk.state is not State.PASS:
                        _kick_notes[_t] = f'{_rk.state.value}[{_rk.code}]'
                        continue
                    # OFFENSIVE TOUCHDOWNS, THIS TEAM, THIS DRAW. Summed from
                    # the sealed matrices by ROW INDEX from _p2_rows, never by
                    # board position -- the layers do not share a row order
                    # and pairing them positionally is the identity defect
                    # this file has already paid for once.
                    _idx = _p2_rows[_t]
                    _td = _np.zeros(int(ds.n_draws), dtype=float)
                    for _lay, _met in (('receiving', 'receiving_td'),
                                       ('rushing', 'rushing_td'),
                                       ('qb', 'rtd'), ('qb', 'ptd')):
                        _mat = _p2.get(f'{_lay}/{_met}')
                        _rows = _idx.get(_lay)
                        if _mat is None or not _rows:
                            continue
                        if _lay == 'qb' and _met == 'ptd':
                            # A PASSING TOUCHDOWN AND ITS RECEPTION ARE ONE
                            # TOUCHDOWN. Both layers carry it -- the passer
                            # gets ptd, the catcher gets receiving_td -- so
                            # adding both would give the kicker twice the
                            # extra-point chances the drive produced. The
                            # receiving side is counted and the passing side
                            # is not, because receiving_td covers every
                            # receiver while a team may have more than one
                            # passer.
                            continue
                        _td += _np.asarray(_mat, float)[list(_rows)].sum(0)
                    _sim = KICK.simulate(_kdoc, _rk.value['gsis_id'],
                                         _np.rint(_td).astype(int),
                                         seed=int(args.seed))
                    _gk = _rk.value['gsis_id']
                    _k_rows.append(_gk)
                    for _m2 in ('fga', 'fgm', 'xpa', 'xpm'):
                        _k_mats.setdefault(_m2, []).append(_sim[_m2])
                    for _b in KICK.BAND_NAMES:
                        _k_mats.setdefault('att_' + _b, []).append(
                            _sim['band_att'][_b])
                        _k_mats.setdefault('made_' + _b, []).append(
                            _sim['band_made'][_b])
                    _k_mats.setdefault('offensive_td', []).append(_td)
                    _k_mats.setdefault('dk_points', []).append(
                        DKS.kicker_points(_sim['band_made'], _sim['xpm']))
                    _k_meta[_gk] = {
                        'team': _t, 'name': _rk.value['name'],
                        'participant_class': _rk.value['participant_class'],
                        'prior_fg_attempts': _rk.value['prior_fg_attempts'],
                        'rate_basis': _rk.as_dict()['evidence']['rate_basis'],
                        'roster_basis': _rk.value['roster_basis'],
                        'roster_source_week': _rk.value['roster_source_week']}
                if _k_rows:
                    o = ds.add_layer(
                        'kicking', _k_rows,
                        {k: _np.stack(v) for k, v in _k_mats.items()},
                        KICK.SPEC_VERSION,
                        'kicking.simulate, conditioned draw-by-draw on this '
                        "team's sealed offensive touchdowns",
                        row_teams={g: v['team'] for g, v in _k_meta.items()})
                    if o.state is not State.PASS:
                        return _fail(o)
                    produced['kicking'] = len(_k_rows)
                    _kick_notes['resolved'] = _k_meta
                    _p2_add('kicking', _k_rows,
                            {k: _np.stack(v) for k, v in _k_mats.items()},
                            lambda g: _k_meta.get(g, {}).get('team'))
            fx['_kicking'] = _kick_notes

            # ---- EVERY RUSHING YARD A PLAYER OWNS, IN ONE PLACE ---------
            #
            # A player's rushing yards were spread across up to three layers:
            # `rushing` (RB carries), `qb` (scrambles and designed runs), and
            # now `gadget_rush` (kneels, jet sweeps, tight-end runs). Nothing
            # published their SUM, so "his rushing yards" had no single answer
            # and DraftKings scored an incomplete one.
            _rt_rows, _rt_tot, _rt_parts = [], {}, {}
            if ds.arrays and not fx.get('distributions'):
                _cand = set()
                for _lay in ('qb', 'rushing', 'gadget_rush'):
                    _cand.update(ds.layers.get(_lay, {}).get('row_ids') or [])

                def _parts_of(pid):
                    """Every rushing-yard vector this player owns."""
                    out = {}
                    for lay, met in (('qb', 'ryds'),
                                     ('rushing', 'rushing_yards')):
                        r = ds.row_index(lay, pid)
                        if r is not None and f'{lay}/{met}' in ds.arrays:
                            out[f'{lay}/{met}'] = ds.vector(lay, met, r)
                    r = ds.row_index('gadget_rush', pid)
                    if r is not None:
                        for cat in ('kneel', 'wr', 'te'):
                            k = f'gadget_rush/{cat}_yards'
                            if k in ds.arrays:
                                out[k] = ds.vector('gadget_rush',
                                                   f'{cat}_yards', r)
                    return out

                for _pid in sorted(_cand):
                    _pv = _parts_of(_pid)
                    if not _pv:
                        continue
                    _rt_rows.append(_pid)
                    _rt_tot[_pid] = sum(_pv.values())
                    _rt_parts[_pid] = {k: round(float(v.mean()), 4)
                                       for k, v in _pv.items()}
                if _rt_rows:
                    o = ds.add_layer(
                        'rushing_total', _rt_rows,
                        {'rushing_yards': _np.stack(
                            [_rt_tot[g] for g in _rt_rows])},
                        'rushing-total-1',
                        'the sum of every rushing yard this player owns, on '
                        'the shared draw index; no randomness of its own',
                        row_teams={g: _team_of_player.get(g)
                                   for g in _rt_rows})
                    if o.state is not State.PASS:
                        return _fail(o)
                    produced['rushing_total'] = len(_rt_rows)
                    # ASSERTED, NOT TRUSTED. Per player, per draw, the
                    # published total equals the sum of its parts --
                    # recomputed from the SEALED matrices rather than from the
                    # variable that built them, because checking an
                    # intermediate value is the defect this file has already
                    # paid for. A tolerance, not ==: these are float sums.
                    _bad = []
                    for _pid in _rt_rows:
                        _chk = sum(_parts_of(_pid).values())
                        _i = ds.row_index('rushing_total', _pid)
                        _d = float(_np.abs(
                            _chk - ds.vector('rushing_total',
                                             'rushing_yards', _i)).max())
                        if _d > 1e-6:
                            _bad.append({'gsis_id': _pid, 'max_abs_dev': _d})
                    if _bad:
                        return _fail(Outcome.fail(
                            'RUSHING_TOTAL_DOES_NOT_CLOSE',
                            f'{len(_bad)} player(s) publish a rushing-yard '
                            f'total that is not the sum of the rushing events '
                            f'they own.', players=_bad[:8]))
                    fx['_rushing_total'] = {
                        'n_players': len(_rt_rows),
                        'closure': 'player rushing yards == sum of every '
                                   'rushing event he owns, EXACT to 1e-6 on '
                                   'every player and every draw',
                        'components': ['qb/ryds', 'rushing/rushing_yards',
                                       'gadget_rush/kneel_yards',
                                       'gadget_rush/wr_yards',
                                       'gadget_rush/te_yards'],
                        'mean_parts': _rt_parts}

            # ---- ONE DRAFTKINGS POINT TOTAL PER SKILL PLAYER ------------
            #
            # Scored from the sealed matrices, on the shared draw index, so a
            # player's point total and the events behind it are the same
            # world. The bonuses are per draw and not applied to a mean --
            # DK pays 3 points for 100 rushing yards IN A GAME, and a mean of
            # 96 that clears 100 in a third of worlds earns a third of the
            # bonus, not none of it.
            _dk_rows, _dk_vecs = [], []
            _all_ids = []
            for _lay in ('qb', 'receiving', 'rushing', 'rushing_total'):
                _all_ids.extend(ds.layers.get(_lay, {}).get('row_ids') or [])
            for _pid in sorted(set(_all_ids)):
                _kw = {}
                for _lay, _pairs in (
                        # `qb/ryds` AND `rushing/rushing_yards` ARE NOT
                        # SCORED HERE. Both are COMPONENTS of rushing_total,
                        # which is scored instead; taking a component and the
                        # total would pay the same yard twice.
                        ('qb', (('pass_yds', 'pyds'), ('pass_td', 'ptd'),
                                ('ints', 'int'), ('rush_td', 'rtd'))),
                        ('receiving', (('rec', 'receptions'),
                                       ('rec_yds', 'receiving_yards'),
                                       ('rec_td', 'receiving_td'))),
                        ('rushing', (('rush_td', 'rushing_td'),)),
                        ('rushing_total',
                         (('rush_yds', 'rushing_yards'),))):
                    _r = ds.row_index(_lay, _pid)
                    if _r is None:
                        continue
                    for _arg, _met in _pairs:
                        if f'{_lay}/{_met}' not in ds.arrays:
                            continue
                        _v = ds.vector(_lay, _met, _r)
                        # A PLAYER CAN RUSH FROM TWO LAYERS. A quarterback's
                        # rushing yards come from the qb layer and a running
                        # back's from the rushing layer; summing rather than
                        # overwriting is what keeps a rushing quarterback who
                        # also appears as a rusher from losing half his yards.
                        _kw[_arg] = _kw.get(_arg, 0.0) + _v
                if _kw:
                    _dk_rows.append(_pid)
                    _dk_vecs.append(DKS.skill_points(int(ds.n_draws), **_kw))
            if _dk_rows:
                o = ds.add_layer(
                    'dk_scoring', _dk_rows,
                    {'dk_points': _np.stack(_dk_vecs)},
                    DKS.SPEC_VERSION,
                    'DraftKings NFL classic scoring applied per draw to this '
                    "run's sealed events; no randomness of its own",
                    row_teams={g: _team_of_player.get(g) for g in _dk_rows})
                if o.state is not State.PASS:
                    return _fail(o)
                produced['dk_scoring'] = len(_dk_rows)

        if not ds.arrays:
            # ABSENCE IS NOT SUCCESS, AND IT IS NAMED.
            #
            # Two different situations, and collapsing them would be the same
            # class of error this whole stage exists to end:
            #
            #  * NOTHING AT ALL. No model layer ran and no fixture was
            #    supplied, so there is no forecast. This is the declared
            #    refusal EMPTY_FORECAST_ARTIFACT, raised HERE rather than three
            #    stages later, so no model runs on a run that has already lost
            #    its forecast.
            #  * A DECLARED FIXTURE RUN. `fx['distributions']` was supplied,
            #    the artifact is already stamped TEST_ONLY and
            #    DISTRIBUTIONS_FROM_FIXTURE, and `artifact.validate` does not
            #    apply the model gates to it. There is genuinely no model draw
            #    set to preserve, and saying so is NOT_APPLICABLE with a
            #    reason -- not PASS, and never a claim that draws were stored.
            inv['draw_set_non_empty'] = Outcome.fail(
                'DRAW_SET_EMPTY',
                'no layer produced a draw matrix, so this run has no '
                'distribution to preserve. Emitting a quantile summary here '
                'would be four numbers with nothing behind them.')
            if not fx.get('distributions'):
                return RF.refuse(
                    'EMPTY_FORECAST_ARTIFACT', 'player_draws',
                    'no model layer produced a draw matrix, so there is no '
                    'distribution to preserve and nothing to seal.', run_id)
            return Outcome.not_applicable(
                'DRAW_SET_NOT_MODEL_PRODUCED',
                'no model layer produced draws; this run carries fixture '
                'distributions and its artifact is stamped TEST_ONLY, so '
                'there is no model draw set to preserve. This is NOT a '
                'forecast and the model gates do not apply to it.',
                distributions_source='FIXTURE_TEST_ONLY')
        inv['draw_set_non_empty'] = Outcome.ok(
            'DRAW_SET_PRESENT', value=len(ds.arrays),
            detail=f'{len(ds.arrays)} matrix(es) from {sorted(produced)}',
            layers=sorted(produced))

        # P2 -- DRAW COHERENCE, ON THE PUBLISHED MATRICES.
        #
        # `include_carries=True` is the declaration this call site is entitled
        # to make and the engine is not: `_p2['team_volume/team_carries']` is
        # the vector that gets sealed, not the SC1-coupled one the engine
        # reads. `shared_pass_live` is READ FROM THE RUN'S COMPONENT LIST, not
        # inferred from the numbers -- three of the closures hold only where
        # the passing line was credited from the receiving event, and guessing
        # the regime from the arrays would be asserting the conclusion.
        #
        # The verdict is stored WHOLE. `assert_draw_coherence` already returns
        # NOT_APPLICABLE for a layer this run does not carry, which is 68 of
        # the 101 sealed runs, and collapsing that to PASS or FAIL is the one
        # thing that would break them: PASS asserts a check that never ran and
        # silence refuses the run with INVARIANT_VERDICT_MISSING.
        fx['_draw_coherence'] = DC.assert_draw_coherence(
            _p2, team_rows=_p2_rows,
            shared_pass_live='C3' in (fx.get('_candidate_applied') or []),
            include_carries='team_volume/team_carries' in _p2)

        w = ds.write(out_dir)
        if w.state is not State.PASS:
            return _fail(w)
        man = w.value
        inv['draw_encoding_lossless'] = Outcome.ok(
            'DRAW_ENCODING_LOSSLESS', value=sorted(
                {e['dtype'] for e in man['arrays'].values()}),
            detail='every matrix round-tripped exactly through its stored '
                   'dtype; nothing was clipped, rounded or rescaled to fit',
            dtypes=sorted({e['dtype'] for e in man['arrays'].values()}))
        inv['draw_index_shared'] = Outcome.ok(
            'DRAW_INDEX_SHARED', value=man['n_draws'],
            detail=f'all {man["n_matrices"]} matrix(es) share one draw index '
                   f'of width {man["n_draws"]}')
        # RE-READ FROM DISK. The write already verified itself; this checks the
        # file the artifact will actually reference, by the hash it will
        # actually record.
        inv['draw_artifact_integrity'] = DA.verify(
            out_dir / DA.DRAW_FILE_NAME, man)
        if inv['draw_artifact_integrity'].state is not State.PASS:
            return inv['draw_artifact_integrity']

        # The quantile view, KEPT -- now with a reference to the draws it came
        # from, so no number in the artifact is unaccompanied by its
        # distribution.
        out, summaries = {}, {}
        for i, r in enumerate(rows if (D is not None and rows) else []):
            pid = r['gsis_id']
            out.setdefault(pid, {})['qb'] = {}
            for f in QBV1.FIELDS:
                q = DA.quantile_view(ds.vector('qb', f, i))
                out[pid]['qb'][f] = dict(
                    q, draws_ref={'key': f'qb/{f}', 'row': i,
                                  'n_draws': man['n_draws'],
                                  'content_digest': man['content_digest']})
                summaries[f'qb/{f}/{pid}'] = q
        # THE NON-QB PLAYERS TOO. The sidecar held 45 receivers and 11 backs
        # while `distributions` carried 8 quarterbacks, so the artifact's own
        # per-player view omitted most of the players it had just forecast. A
        # draw stored but never surfaced is the B13 defect with the sidecar
        # written: the numbers exist and nothing reads them.
        _pay = fx.get('_nonqb_payload')
        if _pay:
            _idx = _pay['index']
            for _layer, _ids, _fields in (
                    ('receiving', _idx['recv_ids'],
                     ('targets', 'receptions', 'receiving_yards',
                      'receiving_td')),
                    ('rushing', _idx['rb_ids'], ('carries', 'rushing_td'))):
                if _layer not in produced:
                    continue
                for i, pid in enumerate(_ids):
                    blk = out.setdefault(pid, {}).setdefault(_layer, {})
                    for f in _fields:
                        q = DA.quantile_view(ds.vector(_layer, f, i))
                        blk[f] = dict(
                            q, draws_ref={'key': f'{_layer}/{f}', 'row': i,
                                          'n_draws': man['n_draws'],
                                          'content_digest':
                                              man['content_digest']})
                        summaries[f'{_layer}/{f}/{pid}'] = q
        cons = DA.assert_summary_consistent(summaries, ds)
        inv['draw_summary_consistency'] = cons
        if cons.state is not State.PASS:
            return cons

        fx['_draw_manifest'] = man
        # `produced` is filled where each layer is actually added, above. It
        # used to be topped up here from `fx['receiving_draws']` and two
        # siblings -- fixture keys nothing in this file ever sets -- so the
        # layer inventory could only ever have been populated by a fixture.
        return Outcome.ok(
            'DRAWS_BUILT', value=out,
            detail=f'{man["n_draw_cells"]} draw cell(s) preserved across '
                   f'{man["n_matrices"]} matrix(es) on one draw index of '
                   f'{man["n_draws"]}; {len(out)} player quantile view(s) kept',
            n_players_with_draws=len(out),
            layers_producing_draws=produced,
            draw_artifact_sha256=man['file']['sha256'],
            draw_content_digest=man['content_digest'],
            n_draw_cells=man['n_draw_cells'],
            draw_bytes=man['file']['bytes'],
            layers_absent=[k for k in
                           ('receiving', 'rushing', 'td', 'team_volume')
                           if k not in produced])
    p.run_stage('player_draws', _draws,
                declared_inputs=['joint'], spec_version='nfl-player-draw-1')
    p.run_stage('scoring', lambda: Outcome.ok(
        'SCORED', value='downstream view only; never an upstream input'),
        declared_inputs=['draws'], spec_version='deterministic')

    def _seal():
        # AN ARTIFACT WITH NO FORECASTS IS NOT A FORECAST ARTIFACT. Without
        # this the pipeline sealed 16 of 16 games carrying `distributions: {}`
        # and reported PASS -- absence read as success, inside the production
        # path itself.
        _dr = next((r for r in p.results if r.stage == 'player_draws'), None)
        # A FIXTURE MAY NOT MASQUERADE AS MODEL OUTPUT. This fell back to
        # `fx['distributions']` -- a dict lifted verbatim out of the
        # --fixtures JSON -- with no trace in the artifact, so a six-line
        # fixture sealed numbers no model computed, the
        # EMPTY_FORECAST_ARTIFACT guard saw a non-empty dict and passed, and
        # eligibility_verdict read 'PASS'. Demonstrated live.
        #
        # The fixture path survives, because the stage-11-to-14 tests need it,
        # but it can no longer be mistaken for a forecast: the artifact
        # records where its numbers came from and stamps itself TEST_ONLY, so
        # provenance travels WITH the numbers instead of being inferable only
        # from how the run was invoked.
        _dist = _dr.value if _dr is not None and _dr.value else {}
        _dist_source = 'MODEL'
        if not _dist and fx.get('distributions'):
            _dist = fx['distributions']
            _dist_source = 'FIXTURE_TEST_ONLY'
        # Which model layers declared themselves unimplemented. Written
        # plainly: an earlier one-liner mixed union and difference, where `-`
        # binds tighter than `|`, so a None survived into sorted() and the
        # sealing stage raised on all 16 games.
        _absent = sorted({r.stage for r in p.results
                          if r.code == 'STAGE_DECLARED_UNIMPLEMENTED'
                          or (r.state == 'NOT_APPLICABLE'
                              and r.stage in NONQB_CHAIN)})
        _completeness = 'COMPLETE' if not _absent else 'PARTIAL_PLAYER_COVERAGE'
        _produced = sorted({r.stage for r in p.results if r.state == 'PASS'
                            and r.stage in ('qb_layer',) + NONQB_CHAIN})
        _eligibility = ('PASS' if _completeness == 'COMPLETE'
                        else 'PARTIAL|PRODUCED:' + ','.join(_produced)
                        + '|ABSENT:' + ','.join(_absent))
        if _dist_source != 'MODEL':
            _eligibility = 'TEST_ONLY|DISTRIBUTIONS_FROM_FIXTURE'
        if _mode['candidate']:
            # A candidate run says so in the field a reader would use to judge
            # eligibility, not only in a field they might not look at.
            _eligibility = (f'{CAND.V1_CANDIDATE}|APPLIED:'
                            + ','.join(fx.get('_candidate_applied') or [])
                            + '|NOT_REACHED:'
                            + ','.join(fx.get('_candidate_not_reached') or [])
                            + '|' + _eligibility)
        if not _dist:
            return RF.refuse('EMPTY_FORECAST_ARTIFACT', 'artifact_sealing',
                             'no model layer produced a player distribution, '
                             'so there is nothing to seal. Sealing an empty '
                             'artifact would report success for a run that '
                             'forecast nothing.', run_id)
        if fx.get('sealing_fails'):
            return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                             'the artifact failed its own contract', run_id)

        # ============================================================
        # B14. ACCOUNTING VERDICTS, AND THE GATE THEY DRIVE
        # ============================================================
        # The defect: verdicts were recorded as display strings and the run
        # continued, so an artifact could represent itself as a valid forecast
        # while carrying FAIL on an invariant the layer rests on.
        #
        # The three-way split is the owner's and is implemented exactly:
        #   HARD invariant FAIL/BLOCKED -> refuse to seal
        #   diagnostic disagreement     -> recorded, not a gate
        #   partial player coverage     -> `completeness`, which already works
        #
        # The classification is NOT decided here. It is read from
        # `artifact.INVARIANTS`, and `artifact.verdict` refuses to accept a
        # class from a call site, so no line in this file can promote a
        # diagnostic or demote an invariant.
        #
        # Scope: verdicts are attached when the numbers came from the MODEL. A
        # fixture-sourced artifact is already stamped TEST_ONLY and is not a
        # forecast, so gating it would assert something about a thing that is
        # declared not to be one.
        _verdicts = None
        if _dist_source == 'MODEL':
            # The diagnostics land in the run's own verdict map too, so
            # run_status.json carries all of them and not only the ones
            # some earlier stage happened to record.
            _inv = fx.setdefault('_inv', {})
            # --- P2 draw coherence ----------------------------------------
            #
            # The verdict was computed at `_draws()` on the matrices that are
            # sealed. It is FILED as an invariant only while
            # `artifact.INVARIANTS` declares the key, because `ART.verdict`
            # refuses a key it does not know and would refuse every artifact
            # this repository can produce. `artifact.py` carries the entry in
            # `PENDING_INVARIANT_REGISTRATION` with that hand-off written down
            # and is owned by another workstream; when the key moves into
            # `INVARIANTS` this emitter feeds it with no further change.
            #
            # It is NEVER silent in the meantime. The state and code go into
            # `run_status.json` either way, so a run whose coherence check
            # failed cannot look like a run that passed one.
            _dcoh = fx.get('_draw_coherence')
            if _dcoh is not None and 'draw_coherence' in ART.INVARIANTS:
                _inv['draw_coherence'] = _dcoh
            # --- diagnostics: recorded on EVERY run, never gating ---------
            _lims = sorted(QBV1.KNOWN_LIMITATIONS)
            _inv['qb_known_limitations'] = (
                Outcome.fail(
                    'QB_LAYER_KNOWN_LIMITATIONS',
                    'characterised weaknesses present in every run of this '
                    'layer: ' + ', '.join(_lims) + '. Measured and reported, '
                    'never smoothed away. This is a statement about how good '
                    'the model is, not about whether its numbers are '
                    'self-consistent, so it does not gate.',
                    limitations=_lims)
                if _lims else
                Outcome.ok('QB_LAYER_NO_KNOWN_LIMITATIONS', value=[],
                           detail='the layer declares none'))
            _warn = fx.get('_qb_team_warnings') or []
            _inv['qb_allocation_residual'] = (
                Outcome.fail(
                    'QB_ALLOCATION_RESIDUAL_PRESENT',
                    '; '.join(_warn)[:380], warnings=_warn)
                if _warn else
                Outcome.ok('QB_ALLOCATION_RESIDUAL_NONE', value=0,
                           detail='the team reconciliation raised no residual '
                                  'warning'))
            _inv['nonqb_layer_availability'] = (
                Outcome.fail(
                    'NONQB_LAYERS_UNAVAILABLE',
                    f'{len(_absent)} completeness layer(s) produced nothing '
                    f'this run: {_absent}. Carried by `completeness` as '
                    f'partial coverage; named here so the artifact says WHICH.',
                    absent=_absent)
                if _absent else
                Outcome.ok('NONQB_LAYERS_ALL_PRODUCED', value=[],
                           detail='every completeness layer produced output'))
            try:
                _verdicts = [ART.verdict(k, o) for k, o in sorted(_inv.items())]
            except (KeyError, TypeError) as exc:
                return RF.refuse('ARTIFACT_SEALING_FAILURE',
                                 'artifact_sealing', str(exc)[:300], run_id)
            _gate = ART.assert_hard_invariants(_verdicts)
            if _gate.state is not State.PASS:
                # THE GATE. A hard invariant that did not hold means there is
                # no valid forecast to publish, whatever else in the run
                # succeeded.
                return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                                 f'{_gate.code}: {_gate.detail}', run_id)
            fx['_gate'] = _gate

        _man = fx.get('_draw_manifest') or {}
        art = {
            'game_id': args.game_id, 'kickoff_utc': kickoff,
            'written_at': args.written_at,
            'source_captures': [{'source': k, 'sha256': v['sha256'],
                                 'retrieved_at': v['retrieved_at']}
                                for k, v in src.items()],
            'model_arm': args.arm, 'spec_hash': run_id,
            'code_commit': commit, 'seed_protocol': f'per-row seed {args.seed}',
            'feature_set_hash': hashlib.sha256(
                json.dumps(sorted(src)).encode()).hexdigest()[:32],
            # NOT A LITERAL. This read 'PASS' unconditionally, asserting
            # eligibility for every run that reached sealing regardless
            # of what the run actually contained.
            'eligibility_verdict': _eligibility,
            'player_ids': [q['gsis_id'] for q in fx.get('players', [])],
            'team_ids': fx.get('team_ids', []),
            # TWO ORDERINGS OF "TEAM" LIVE IN ONE ARTIFACT AND THEY DIFFER.
            # `team_ids` is away-then-home, from the game id. The team_volume
            # draw matrices are stacked in SORTED team order, which is the
            # layer's own `row_ids` in the draw manifest. Both are correct and
            # neither is wrong to hold; what was missing was anything binding
            # them, so a reader who indexed the matrix by `team_ids` got the
            # other team's numbers and no check anywhere objected. That is
            # exactly how the "SF 0.942 / LA 1.060 QB ownership leak" was
            # reported in the R6 and R7 audits for a quantity that in fact
            # closes exactly. The map is now written down.
            'team_draw_row_index': fx.get('_team_draw_row_index') or {},
            # THE KICKER'S IDENTITY TRAVELS WITH HIS DRAWS. Sealing the
            # kicking matrices while leaving the kicker as a bare gsis_id in
            # the manifest would publish sixteen metrics nobody can attribute
            # to a club, a name, a participation class or the roster week the
            # name came from. That last one matters most: there is no week-2
            # roster capture, so the kicker is carried forward from week 1 and
            # the artifact has to SAY he is carried forward rather than let a
            # reader assume the roster was checked today. Refusals for clubs
            # with no resolvable kicker are recorded here too, because a club
            # that produced no kicking line must be visible as such.
            'kicking': fx.get('_kicking') or {},
            # WHO TOOK THE CARRIES THAT USED TO HAVE NOBODY, and
            # which categories were deliberately left unnamed.
            'gadget_rush': fx.get('_gadget_rush') or {},
            # WHO THE CURRENT-STATE FEED REMOVED, AND ON WHAT.
            'availability': fx.get('_availability') or {},
            # EVERY RUSHING YARD IN ONE PLACE, AND ITS CLOSURE.
            'rushing_total': fx.get('_rushing_total') or {},
            # THE CLOSURE PROOF, QUANTIFIED, IN THE ARTIFACT ITSELF. Every team
            # dropback belongs to exactly one quarterback on that team, and a
            # reader should not have to re-derive that from the draw matrices
            # -- which is where the transposition above came from in the first
            # place.
            'qb_team_dropback_closure':
                ((fx.get('_qb_accounting') or {}).get('team') or {}).get(
                    'per_team_dropback_closure') or
                {'status': 'NOT_MEASURED',
                 'why': 'the QB team reconciliation did not run in this run'},
            'distributions': _dist,
            'distributions_source': _dist_source,
            # WHICH MODEL PRODUCED THIS NUMBER, answered by the artifact
            # rather than by reconstructing an invocation.
            'model_configuration': _mode['mode'],
            'candidate_components': _mode['components'],
            'candidate_components_applied': fx.get('_candidate_applied') or [],
            'candidate_components_not_reached':
                fx.get('_candidate_not_reached') or [],
            # PRESENT ONLY WHEN C3 WAS REACHED AND REFUSED. Absent means the
            # question did not arise; it never means the answer was yes.
            **({'c3_refusal': fx['_c3_refusal'],
                'seal_contract_c3': C3_REFUSAL_CONTRACT}
               if fx.get('_c3_refusal') else
               {'seal_contract_c3': C3_REFUSAL_CONTRACT}),
            'promoted': False,
            'prospective_eligible': False,
            'TEST_ONLY': _dist_source != 'MODEL',
            'completeness': _completeness,
            'absent_layers': _absent,
            'excluded_unidentified': fx.get('_excluded_unidentified', []),
            'contract_version': ART.CONTRACT_VERSION,
            # B13. The distribution itself, by hash. The bytes stay in the
            # sidecar; the artifact carries the identity that changes if any
            # single draw changes, plus the manifest a reader needs to open it.
            'draw_artifact_sha256': (_man.get('file') or {}).get('sha256'),
            'draw_artifact': _man or None,
            # B14. Every declared invariant's verdict travels WITH the numbers.
            'accounting_verdicts': _verdicts,
        }
        # A CANDIDATE RUN MAY NOT LOOK LIKE THE PROMOTED MODEL. Checked at the
        # seal, on the assembled artifact, so it cannot be satisfied by an
        # invocation-time flag that a later edit forgets to carry.
        nm = CAND.assert_not_promoted(_mode['mode'], art)
        if nm.state is State.FAIL:
            return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                             f'{nm.code}: {nm.detail[:220]}', run_id)
        v = ART.validate(art)
        if v.state is not State.PASS:
            return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                             f'{v.code}: {v.detail[:200]}', run_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'forecast_artifact.json').write_text(
            json.dumps(art, indent=1, sort_keys=True) + '\n')
        return Outcome.ok(
            'ARTIFACT_SEALED', value=ART.artifact_id(art),
            detail=(f'{(_man.get("n_draw_cells") or 0)} draw cell(s) '
                    f'referenced by sha256'
                    + (f'; {fx["_gate"].detail}'
                       if fx.get('_gate') is not None else '')),
            draw_artifact_sha256=(_man.get('file') or {}).get('sha256'),
            n_hard_invariants=len(ART.HARD_INVARIANTS),
            n_diagnostic_invariants=len(ART.DIAGNOSTIC_INVARIANTS),
            hard_owed=(fx['_gate'].evidence.get('hard_owed')
                       if fx.get('_gate') is not None else None),
            diagnostics_not_clean=(
                fx['_gate'].evidence.get('diagnostics_not_clean')
                if fx.get('_gate') is not None else None))
    p.run_stage('artifact_sealing', _seal, declared_inputs=['draws'],
                spec_version=ART.CONTRACT_VERSION)

    summary = p.summary()
    # The run's own record of the draw set and of every invariant verdict, so
    # `run_status.json` answers both B13 and B14 questions without opening the
    # artifact.
    _m = fx.get('_draw_manifest') or {}
    summary['draw_artifact'] = ({'sha256': (_m.get('file') or {}).get('sha256'),
                                 'bytes': (_m.get('file') or {}).get('bytes'),
                                 'n_draws': _m.get('n_draws'),
                                 'n_matrices': _m.get('n_matrices'),
                                 'n_draw_cells': _m.get('n_draw_cells'),
                                 'content_digest': _m.get('content_digest')}
                                if _m else None)
    summary['accounting_verdicts'] = [
        {'invariant': k, 'class': ART.INVARIANTS[k]['class'],
         'state': o.state.value, 'code': o.code}
        for k, o in sorted(fx.get('_inv', {}).items())
        if k in ART.INVARIANTS]
    _own = fx.get('_qb_ownership')
    # P2 COHERENCE, RECORDED WHETHER OR NOT IT IS YET AN INVARIANT KEY.
    # `accounting_verdicts` above can only carry keys `artifact.INVARIANTS`
    # declares; this says what the check found regardless, so the period
    # before the registration lands is visible rather than blank.
    _dc = fx.get('_draw_coherence')
    summary['draw_coherence'] = (
        None if _dc is None else
        {'state': _dc.state.value, 'code': _dc.code,
         'detail': _dc.detail[:400],
         'spec_version': _dc.evidence.get('spec_version'),
         'components': _dc.evidence.get('components'),
         'registered_as_invariant': 'draw_coherence' in ART.INVARIANTS,
         'gating': ('draw_coherence' in ART.INVARIANTS
                    and ART.INVARIANTS.get('draw_coherence', {}).get('class')
                    == 'HARD')})
    # THE CONFIDENCE INPUTS THAT EXIST BEFORE THE SEAL, SEALED WITH IT.
    #
    # `run_status.json` is one of the files the seal manifest hashes, so a
    # value recorded here is fixed at forecast time and cannot be restored
    # afterwards from knowledge of the outcome. `readiness` is the input
    # `confidence.score_player` consumes for `status_certainty`, and it is the
    # one dimension NOT recoverable from the seal: the other four are
    # recomputable from the sealed draws and the artifact's source captures.
    # The contract pins the dimensions and weights in force at forecast time,
    # so a later reweighting cannot silently reinterpret a stored row.
    #
    # Both are supplied by the caller, from captures and the chronology cut.
    # Neither reads anything this run wrote. A run sealed before this change
    # carries neither key -- absence stays absence and is not backfilled.
    summary['readiness'] = fx.get('readiness')
    summary['confidence_contract'] = fx.get('confidence_contract')
    summary['qb_inactive_ownership'] = _own
    summary['qb3_configuration'] = fx.get('_qb3_config')
    # THE ELIGIBILITY VERDICT FOR THE QUARTERBACK POOL, AND WHAT IT DOES NOT
    # REPAIR. Absent on a run that did not filter -- absence stays absence and
    # is never backfilled into a sealed artifact.
    summary['qb_pool_eligibility'] = fx.get('_r5_qb')
    summary['qb_participation_limitation'] = (
        QB_PARTICIPATION_LIMITATION if fx.get('_r5_qb_applied') else None)
    summary['qb_inactive_ownership_enforced'] = bool(
        (_own or {}).get('enforced'))
    summary['execution_identity'] = execution_identity(args, src, commit)
    summary['code_commit'] = commit
    # THE MATERIAL BEHIND THE DIGEST, not only the digest. A digest nobody can
    # reconstruct is a number a reader can compare and cannot audit, and that
    # is what made working-tree state NOT_RECOVERABLE on every sealed run
    # tested. Source content only: `code_identity` excludes every subtree a
    # run writes into, so nothing recorded here reads this run's own outputs.
    summary['code_identity'] = (
        fx['_code_identity'].value
        if fx.get('_code_identity') is not None
        and fx['_code_identity'].state is State.PASS
        else {'state': fx['_code_identity'].state.value,
              'code': fx['_code_identity'].code,
              'detail': fx['_code_identity'].detail[:300]}
        if fx.get('_code_identity') is not None else None)
    summary['dry_run'] = bool(args.dry_run)
    summary['prospective_eligible'] = False if args.dry_run else None
    # publication is a SEPARATE gate and is checked last, never assumed
    pub = AUTH.may_publish()
    summary['publication'] = {'state': pub.state.value, 'code': pub.code,
                              'detail': pub.detail[:200]}
    p.out_dir.mkdir(parents=True, exist_ok=True)
    (p.out_dir / 'run_status.json').write_text(
        json.dumps(summary, indent=1, default=str) + '\n')
    RF.persist(p.refusals, p.out_dir)
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--game-id', required=True)
    ap.add_argument('--arm', required=True, choices=ARMS)
    ap.add_argument('--written-at', required=True,
                    help='REQUIRED. There is no wall-clock default for a '
                         'scientific clock.')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--seed', type=int, default=20260908)
    ap.add_argument('--dry-run', action='store_true',
                    help='historical fixture run; NEVER prospective evidence')
    ap.add_argument('--fixtures', default=None)
    ap.add_argument('--model-configuration', dest='model_configuration',
                    default=CAND.PRODUCTION_BASELINE,
                    help='PRODUCTION_BASELINE (default) or V1_CANDIDATE. '
                         'The candidate configuration is explicit and '
                         'never the default; an unknown name is refused '
                         'rather than falling back to the baseline.')
    a = ap.parse_args(argv)
    fx = json.loads(pathlib.Path(a.fixtures).read_text()) if a.fixtures else {}
    s = build(a, fx)
    print(f"run {s['run_id']}  arm {s['arm']}  status {s['status']}  "
          f"{s['elapsed_s']:.3f}s"
          + ('  [DRY RUN -- not prospective evidence]' if a.dry_run else ''))
    for r in s['stages']:
        mark = {'PASS': 'ok  ', 'BLOCKED': 'STOP', 'FAIL': 'FAIL'}.get(
            r['state'], r['state'])
        print(f"  {mark} {r['stage']:<24}{r['code']}")
        if r['state'] != 'PASS':
            print(f"       {r['detail'][:160]}")
    print(f"  publication: {s['publication']['code']}")
    return 0 if s['status'] == 'SEALED' else 1


if __name__ == '__main__':
    sys.exit(main())
