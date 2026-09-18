"""Portfolio exposure governance, and the one rule that would have stopped it.

    PORTFOLIO_MAY_NOT_BE_AUTHORIZED_IF_HIGH_EXPOSURE_IS_DRIVEN_BY_A_KNOWN_MODEL_DEFECT

A legal portfolio is not a governed one. The 2026-09-17 DET @ BUF portfolio
passed every rule DraftKings has -- salary, roster shape, both teams, no
duplicate player, forty unique lineups -- and put 72.5% of its lineups on the
player the model was most demonstrably wrong about. Legality had nothing to
say about it, because legality is a statement about the SITE'S constraints and
this is a statement about OUR evidence.

WHAT THIS MODULE DOES NOT DO

It does not decide who is good. It reads a built portfolio, counts exposure,
compares each player's exposure against the cap his CONFIDENCE TAG carries,
and refuses when a capped player is over. It is an audit, and it runs after
construction on purpose: an optimizer that enforced its own caps would be
marking its own homework, and the audit has to be able to fail a portfolio
that some future optimizer built by a route nobody here anticipated.
"""
from __future__ import annotations

import collections
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production.dfs import projection_confidence as PC           # noqa: E402

SPEC_VERSION = 'nfl-dfs-portfolio-guard-1'

CODE_OK = 'PORTFOLIO_EXPOSURE_WITHIN_POLICY'
CODE_DEFECT_DRIVEN = 'PORTFOLIO_EXPOSURE_DRIVEN_BY_KNOWN_DEFECT'
CODE_BLOCKED_PLAYER = 'PORTFOLIO_CONTAINS_BLOCKED_PLAYER'
CODE_UNTAGGED = 'PORTFOLIO_CONTAINS_UNTAGGED_PLAYER'
CODE_OVERRIDE_UNEVIDENCED = 'PORTFOLIO_OVERRIDE_CARRIES_NO_EVIDENCE'

HARD_CODES = (CODE_DEFECT_DRIVEN, CODE_BLOCKED_PLAYER, CODE_UNTAGGED,
              CODE_OVERRIDE_UNEVIDENCED)


def exposures(lineups):
    """{player: share of lineups} and {player: share at captain}.

    `lineups` is a sequence of {'captain': id, 'flex': [id, ...]}.
    """
    n = len(lineups)
    any_, cpt = collections.Counter(), collections.Counter()
    for lu in lineups:
        c = lu['captain']
        cpt[c] += 1
        for p in [c] + list(lu['flex']):
            any_[p] += 1
    return ({p: v / n for p, v in any_.items()},
            {p: v / n for p, v in cpt.items()}, n)


def audit(lineups, tags: dict, *, overrides: dict = None,
          label: str = 'portfolio') -> Outcome:
    """Refuse a portfolio whose concentration rests on a tagged defect."""
    if not lineups:
        return Outcome.fail(
            'PORTFOLIO_EMPTY',
            'an empty portfolio is not a portfolio that passed.',
            cause=Cause.DATA)
    overrides = overrides or {}
    any_, cpt, n = exposures(lineups)
    t = PC.assert_every_player_tagged(list(any_), tags)
    if t.state is not State.PASS:
        # `t.evidence` already carries its own `cause`; re-passing it
        # alongside the keyword is a TypeError, and `cause` is a reserved
        # kwarg on Outcome the same way `code` is.
        return Outcome.fail(
            CODE_UNTAGGED, t.detail, cause=Cause.GOVERNANCE,
            label=label,
            **{k: v for k, v in t.evidence.items() if k != 'cause'})
    rows, violations, blocked = {}, [], []
    for p, share in sorted(any_.items(), key=lambda kv: -kv[1]):
        tag = tags[p]
        pol = PC.POLICY[tag]
        c = cpt.get(p, 0.0)
        ov = overrides.get(p)
        row = {'tag': tag, 'exposure': round(share, 4),
               'captain_exposure': round(c, 4),
               'max_exposure': pol['max_exposure'],
               'max_captain_exposure': pol['max_captain_exposure'],
               'blocked_by_tag': pol['blocked'], 'override': ov}
        if pol['blocked'] and share > 0:
            blocked.append(p)
        over_any = (pol['max_exposure'] is not None
                    and share > pol['max_exposure'] + 1e-12)
        over_cpt = (pol['max_captain_exposure'] is not None
                    and c > pol['max_captain_exposure'] + 1e-12)
        if (over_any or over_cpt) and not pol['blocked']:
            if ov is None:
                violations.append({'player': p, 'tag': tag,
                                   'exposure': round(share, 4),
                                   'cap': pol['max_exposure'],
                                   'captain_exposure': round(c, 4),
                                   'captain_cap': pol['max_captain_exposure'],
                                   'over_any': over_any,
                                   'over_captain': over_cpt})
            elif not str(ov).strip():
                return Outcome.fail(
                    CODE_OVERRIDE_UNEVIDENCED,
                    f'{p} carries an override with no evidence. An override '
                    f'is a claim that new evidence beats the recorded defect, '
                    f'so it has to say what the evidence is.',
                    cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION,
                    player=p, label=label)
        rows[p] = row
    ev = {'spec_version': SPEC_VERSION, 'label': label, 'n_lineups': n,
          'rows': rows, 'violations': violations,
          'blocked_players_present': sorted(blocked),
          'rule': 'PORTFOLIO_MAY_NOT_BE_AUTHORIZED_IF_HIGH_EXPOSURE_IS_'
                  'DRIVEN_BY_A_KNOWN_MODEL_DEFECT'}
    if blocked:
        return Outcome.fail(
            CODE_BLOCKED_PLAYER,
            f'{label}: {sorted(blocked)} carry a blocking tag and appear in '
            f'the portfolio anyway.', cause=Cause.GOVERNANCE, **ev)
    if violations:
        worst = max(violations, key=lambda v: v['exposure'])
        return Outcome.fail(
            CODE_DEFECT_DRIVEN,
            f'{label}: {len(violations)} player(s) exceed the exposure their '
            f'confidence tag allows, worst {worst["player"]} at '
            f'{worst["exposure"]:.1%} against a {worst["cap"]:.0%} cap for '
            f'{worst["tag"]}. The optimizer did what the numbers told it; the '
            f'numbers already carried a recorded defect.',
            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok(
        CODE_OK, value=rows,
        detail=f'{label}: {n} lineup(s), every exposure within the policy its '
               f'confidence tag carries', **ev)


def authorize(lineups, tags: dict, *, overrides: dict = None,
              label: str = 'portfolio') -> Outcome:
    """The authorization gate. A refusal here is not advice; it is a stop."""
    a = audit(lineups, tags, overrides=overrides, label=label)
    if a.state is not State.PASS:
        return a
    return Outcome.ok(
        'PORTFOLIO_AUTHORIZED', value=a.value,
        detail=f'{label}: authorized on exposure policy ONLY. This says '
               f'nothing about whether the portfolio is good, only that no '
               f'concentration rests on a tagged defect.',
        **a.evidence)
