#!/usr/bin/env python3.12
"""Hard Rock player props against the sealed football distributions: a diagnostic, never a pick.

    python3.12 nfl/tools/classic_prop_compare.py 2026W4 [--boards nfl/market/raw/HR_*_BOARD_*.csv]

ORDER, ENFORCED. The proprietary distributions are fixed by DK_<slate>_EARLY_SEAL.json (projection
and worlds hashes, written when the research book was built). Every price passes through
nfl/market/price_history.comparable(seal, price): a price captured before the seal, or after kickoff,
is refused by name. This module runs in its own process, imports no projection code, and writes only
its own diagnostic file. Nothing it computes travels back into a projection, a draw or a lineup.

WHAT A ROW SAYS. For each two-sided player market: the line, our mean, median, p25, p75, p90, P(over)
and P(under) READ FROM THE STORED WORLDS (never from percentiles), Hard Rock's no-vig probability
(multiplicative de-vig of the two posted prices), and the football decomposition -- what has to
happen for each side: volume, efficiency, game script and the player's uncertainty, taken from the
same research book the DFS portfolio was built on.

WHAT "ATTENTION" MEANS. A row is flagged for attention only when our P(over) and Hard Rock's no-vig
P(over) differ by at least ATTENTION_GAP AND the player's evidence is not low-quality (no low-confidence
prior, no Questionable/Doubtful designation, no chart-only starter, no unresolved role conflict).
ATTENTION_GAP is a DECLARED reading threshold, not a measured edge: PROJECTION_SYSTEM_STATE is
NOT_VALIDATED, so no row here is a recommendation and none may be read as one.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import pathlib
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.market import price_history as PH  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
#: DECLARED reading threshold (probability points). Not an edge, not a bet trigger.
ATTENTION_GAP = 0.10
#: Hard Rock market -> how the outcome is read off a stored world
MARKETS = {
    'player_passing_yards': ('pass_yards',), 'player_passing_attempts': ('pass_att',),
    'player_passing_touchdowns': ('pass_td',), 'player_interceptions': ('interceptions',),
    'player_rushing_yards': ('rush_yards',), 'player_rushing_attempts': ('carries',),
    'player_receptions': ('receptions',), 'player_receiving_yards': ('rec_yards',),
    'player_rushing_+_receiving_yards': ('rush_yards', 'rec_yards'),
    'player_touchdowns': ('rush_td', 'rec_td'),
}
NOT_DRAWN = {'player_passing_completions', 'player_longest_reception', 'player_longest_rush',
             'player_longest_passing_completion', 'player_kicking_points', 'player_field_goals_made'}
VOLUME_OF = {'pass_yards': 'pass_att', 'rec_yards': 'targets', 'rush_yards': 'carries', 'receptions': 'targets',
             'pass_td': 'pass_att', 'interceptions': 'pass_att'}


def american_to_prob(a):
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def no_vig(over, under):
    """Multiplicative de-vig of a two-sided price. None when a side is missing."""
    if over in (None, '') or under in (None, ''):
        return None
    po, pu = american_to_prob(over), american_to_prob(under)
    return po / (po + pu)


def _norm(s):
    return re.sub(r'[^a-z]', '', re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', (s or '').lower()))


def _load_sealed(slate_id):
    seal_p, book_p = OUT_DIR / f'DK_{slate_id}_EARLY_SEAL.json', OUT_DIR / f'DK_{slate_id}_EARLY_RESEARCH_BOOK.json'
    wp = OUT_DIR / f'DK_{slate_id}_EARLY_WORLDS.npz'
    for p in (seal_p, book_p, wp):
        if not p.exists():
            return Outcome.blocked('PROPS_NOT_SEALED', f'{p.name} missing: build and seal the research book first',
                                   cause=Cause.NOT_EXECUTED)
    seal = json.loads(seal_p.read_text())
    if hashlib.sha256(wp.read_bytes()).hexdigest() != seal['worlds_sha256'] or \
            hashlib.sha256(book_p.read_bytes()).hexdigest() != seal['research_book_sha256']:
        return Outcome.fail('PROPS_SEAL_DOES_NOT_MATCH', 'the worlds or the research book changed after the seal')
    z = np.load(wp)
    meta = json.loads(bytes(z['meta']).decode())
    return Outcome.ok('PROPS_SEALED_INPUTS', value={'seal': seal, 'book': json.loads(book_p.read_text()),
                                                    'stats': z['stats'], 'points': z['points'], 'meta': meta})


def outcome_vector(stats_row, fields, yard_scale, parts):
    F = {f: i for i, f in enumerate(fields)}
    v = np.zeros(stats_row.shape[0])
    for f in parts:
        a = stats_row[:, F[f]].astype(float)
        v += a / yard_scale if f.endswith('yards') else a
    return v


def decompose(card, market, parts, line, stats_row, fields, ys, margin):
    """What has to happen for the over, in football quantities, from the same worlds."""
    F = {f: i for i, f in enumerate(fields)}
    x = outcome_vector(stats_row, fields, ys, parts)
    over = x > line
    out = {'role': (card.get('role_types') or []) + [f"band {card['projection'].get('role_band')}"],
           'injury_effect': card['uncertainty']['conflicts'] or 'none recorded',
           'main_uncertainty': ', '.join(filter(None, [
               f"prior {card['uncertainty']['role_confidence']}",
               f"availability {card['status']['availability']} ({card['status']['designation'] or 'no designation'})",
               f"{card['measured_2026']['games']} games of 2026 evidence"]))}
    vol = VOLUME_OF.get(parts[0]) if len(parts) == 1 else None
    if vol:
        v = stats_row[:, F[vol]].astype(float)
        out['volume'] = {'field': vol, 'mean': round(float(v.mean()), 2),
                         'p10_p50_p90': [round(float(np.percentile(v, q)), 1) for q in (10, 50, 90)],
                         'mean_when_over_wins': round(float(v[over].mean()), 2) if over.any() else None,
                         'mean_when_under_wins': round(float(v[~over].mean()), 2) if (~over).any() else None}
        if parts[0].endswith('yards') and v.mean() > 0:
            out['efficiency'] = {'line_needs_per_' + vol: round(line / v.mean(), 2),
                                 'our_projected_rate': round(float(x.sum() / max(v.sum(), 1e-9)), 2)}
    if margin is not None:
        lead, trail = margin >= 8, margin <= -8
        out['game_script'] = {'p_over_if_own_team_trails_by_8+': round(float(over[trail].mean()), 3) if trail.sum() >= 50 else None,
                              'p_over_if_own_team_leads_by_8+': round(float(over[lead].mean()), 3) if lead.sum() >= 50 else None,
                              'MARGIN_IS': 'simulated final margin'}
    out['to_win_over'] = {
        'player_active': 'required (worlds assume he plays; a scratch voids or loses per house rules)',
        **({'needs': f"more than {line} {market.replace('player_', '').replace('_', ' ')}"}),
    }
    return out


def low_quality(card):
    u, s = card['uncertainty'], card['status']
    return bool(u['role_confidence'] in ('LOW', None) or s['designation'] in ('QUESTIONABLE', 'DOUBTFUL')
                or s['reported_starter'] or u['conflicts'])


def compare(slate_id, boards):
    so = _load_sealed(slate_id)
    if so.state.value != 'PASS':
        return so
    S = so.value
    seal, book, stats, meta = S['seal'], S['book'], S['stats'], S['meta']
    fields, ys = list(meta['fields']), meta['yard_scale']
    kix = {k: i for i, k in enumerate(meta['keys'])}
    gix = {g['game_id']: i for i, g in enumerate(meta['games'])}
    cards = {}
    for gid, g in book['games'].items():
        for club, t in g['teams'].items():
            for c in t['players']:
                cards.setdefault((gid, _norm(c['name'])), []).append((club, t['home'], c))
    files = [pathlib.Path(b) for b in boards] if boards else sorted(
        pathlib.Path(p) for p in glob.glob(str(PH.RAW_DIR / 'HR_*_BOARD_*.csv')))
    games_by_clubs = {frozenset((g['away'], g['home'])): gid for gid, g in book['games'].items()}
    rows, refused = [], []
    for f in files:
        m = re.match(r'HR_([A-Z]{2,3})_([A-Z]{2,3})_BOARD_', f.name)
        clubs = frozenset(m.groups()) if m else None
        gid = games_by_clubs.get(clubs) or games_by_clubs.get(frozenset({'LA' if c == 'LAR' else c for c in clubs or ()}))
        if gid is None:
            refused.append({'file': f.name, 'why': 'NOT_A_GAME_ON_THIS_SLATE'})
            continue
        lo = PH.load_board(f)
        if lo.state.value != 'PASS':
            refused.append({'file': f.name, 'why': lo.code, 'detail': lo.detail})
            continue
        sides = {}
        for ob in lo.value['observations']:
            if ob['side'] in ('OVER', 'UNDER') and ob['market'].startswith('player_'):
                sides.setdefault((ob['market'], ob['selection'], ob['points'], ob['is_main']), {})[ob['side']] = ob
        for (mk, sel, pts_, main), sd in sides.items():
            base = sd.get('OVER') or sd.get('UNDER')
            if mk in NOT_DRAWN:
                refused.append({'market': mk, 'player': sel, 'why': 'MARKET_NOT_DRAWN_BY_THE_SIMULATOR'})
                continue
            if mk not in MARKETS:
                refused.append({'market': mk, 'player': sel, 'why': 'MARKET_UNMAPPED'})
                continue
            cmpb = PH.comparable(seal, base)
            if cmpb.state.value != 'PASS':
                refused.append({'market': mk, 'player': sel, 'line': pts_, 'why': cmpb.code})
                continue
            hit = cards.get((gid, _norm(sel)), [])
            if len(hit) != 1:
                refused.append({'market': mk, 'player': sel, 'why': 'PLAYER_NOT_MATCHED' if not hit else 'PLAYER_AMBIGUOUS'})
                continue
            club, home, card = hit[0]
            if card['key'] not in kix:
                refused.append({'market': mk, 'player': sel, 'why': 'PLAYER_HAS_NO_STORED_WORLDS'})
                continue
            line = float(pts_)
            parts = MARKETS[mk]
            st = stats[kix[card['key']]]
            x = outcome_vector(st, fields, ys, parts)
            push = (x == line).mean()
            p_over, p_under = float((x > line).mean()), float((x < line).mean())
            book_p = no_vig((sd.get('OVER') or {}).get('price'), (sd.get('UNDER') or {}).get('price'))
            pts_g = S['points'][gix[gid]]
            margin = (pts_g[:, 0] - pts_g[:, 1]) * (1 if club == book['games'][gid]['home'] else -1)
            gap = (p_over - book_p) if book_p is not None else None
            lq = low_quality(card)
            rows.append({
                'game_id': gid, 'player': card['name'], 'team': club, 'position': card['position'],
                'market': mk, 'hard_rock_line': line, 'is_main': main,
                'over_price': (sd.get('OVER') or {}).get('price'), 'under_price': (sd.get('UNDER') or {}).get('price'),
                'price_ts_utc': base['ts_utc'],
                'model_mean': round(float(x.mean()), 2), 'model_median': round(float(np.median(x)), 2),
                'p25': round(float(np.percentile(x, 25)), 2), 'p75': round(float(np.percentile(x, 75)), 2),
                'p90': round(float(np.percentile(x, 90)), 2),
                'p_over': round(p_over, 4), 'p_under': round(p_under, 4), 'p_push': round(float(push), 4),
                'hard_rock_no_vig_p_over': round(book_p, 4) if book_p is not None else None,
                'gap_p_over': round(gap, 4) if gap is not None else None,
                'evidence_low_quality': lq,
                'ATTENTION': bool(gap is not None and abs(gap) >= ATTENTION_GAP and not lq),
                'decomposition': decompose(card, mk, parts, line, st, fields, ys, margin),
            })
    doc = {'ARTIFACT': 'CLASSIC_PROP_DIAGNOSTIC', 'slate_id': slate_id,
           'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'seal': seal,
           'boards': [f.name for f in files], 'n_rows': len(rows), 'n_attention': sum(r['ATTENTION'] for r in rows),
           'ATTENTION_GAP': (ATTENTION_GAP, 'declared reading threshold, not a measured edge'),
           'NOT_A_RECOMMENDATION': 'PROJECTION_SYSTEM_STATE is NOT_VALIDATED. No row is a bet.',
           'rows': sorted(rows, key=lambda r: -abs(r['gap_p_over'] or 0)), 'refused': refused}
    out = OUT_DIR / f'DK_{slate_id}_EARLY_PROP_DIAGNOSTIC.json'
    out.write_text(json.dumps(doc, indent=1))
    on_slate = [f for f in files if not any(r.get('file') == f.name and r['why'] == 'NOT_A_GAME_ON_THIS_SLATE'
                                            for r in refused)]
    if not on_slate:
        return Outcome.blocked('PROPS_NO_HARD_ROCK_BOARD', 'no Hard Rock board for this slate is held; '
                               'requested from the networked agent in docs/AGENT_OUTBOX.md', cause=Cause.DATA)
    if not rows:
        return Outcome.blocked('PROPS_NO_COMPARABLE_ROW', f'{len(refused)} row(s) refused, none comparable',
                               cause=Cause.DATA, refused=refused[:10])
    return Outcome.measured('PROPS_COMPARED', {'n_rows': len(rows)}, n_measured=len(rows), what='comparable prop sides',
                            detail=f"{len(rows)} rows, {doc['n_attention']} flagged for attention, {len(refused)} refused")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--boards', nargs='*')
    a = ap.parse_args()
    o = compare(a.slate_id, a.boards)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
