"""Render a board as something a person reads without opening JSON."""
from __future__ import annotations

from nfl.product import metrics as M

# Which metrics lead each position's table, in reading order.
COLUMNS = {
    'QB': [('qb', 'att'), ('qb', 'cmp'), ('qb', 'pyds'), ('qb', 'ptd'),
           ('qb', 'int'), ('qb', 'rush_opp'), ('qb', 'ryds'),
           ('qb', 'sacks')],
    'RB': [('rushing', 'carries'), ('receiving', 'targets'),
           ('receiving', 'receptions'), ('receiving', 'receiving_yards')],
    'WR': [('receiving', 'targets'), ('receiving', 'receptions'),
           ('receiving', 'receiving_yards')],
    'TE': [('receiving', 'targets'), ('receiving', 'receptions'),
           ('receiving', 'receiving_yards')],
}
TITLES = {'QB': 'Quarterbacks', 'RB': 'Running backs',
          'WR': 'Wide receivers', 'TE': 'Tight ends'}

MARK = {M.MODELED: '', M.PROVISIONAL: ' *', M.UNAVAILABLE: ' --'}


def _name(row, names):
    n = names.get(row['gsis_id'])
    tag = row.get('depth_chart')
    who = n or row['gsis_id']
    return f'{who} ({row["team"]}{"" if not tag else " " + tag})'


def _num(v, kind):
    if v is None:
        return '--'
    return f'{v:.0f}' if kind == 'count' else f'{v:.1f}'


def player_table(rows, position, names):
    cols = COLUMNS.get(position, [])
    if not rows:
        return [f'_No {TITLES.get(position, position).lower()} with a '
                f'forecast distribution in this game._', '']
    out = ['| Player | Metric | Mean | P10 | P25 | P50 | P75 | P90 |',
           '|---|---|--:|--:|--:|--:|--:|--:|']
    for r in rows:
        first = True
        for layer, key in cols:
            m = r['metrics'].get(f'{layer}/{key}')
            if not m:
                continue
            k = m['kind']
            out.append('| {} | {}{} | {} | {} | {} | {} | {} | {} |'.format(
                _name(r, names) if first else '',
                m['label'], MARK.get(m['status'], ''),
                _num(m['mean'], k), _num(m['p10'], k), _num(m['p25'], k),
                _num(m['p50'], k), _num(m['p75'], k), _num(m['p90'], k)))
            first = False
        if not first:
            sh = r.get('opportunity_share') or {}
            bits = [f'{k.split("/")[1]} {v["share_of_game_pool"]:.1%}'
                    for k, v in sorted(sh.items())]
            conf = r['confidence']
            out.append('| | _share: {}_ | | | | | | _conf {:.2f}_ |'.format(
                ', '.join(bits) if bits else 'n/a', conf['score']))
    out.append('')
    return out


def threshold_block(rows, position, names, wanted):
    out = []
    for r in rows:
        lines = []
        for layer, key in wanted:
            m = r['metrics'].get(f'{layer}/{key}')
            if not m or not m['thresholds']:
                continue
            probs = '  '.join(f'{t["threshold"]} **{t["p"]:.0%}**'
                              for t in m['thresholds'])
            lines.append(f'- {m["label"]}: {probs}')
        if lines:
            out.append(f'**{_name(r, names)}**')
            out.extend(lines)
            out.append('')
    return out


def render(board, names=None) -> str:
    names = names or {}
    a = board['authorization']
    f = board['freshness']
    away, home = (board['teams'] + ['?', '?'])[:2]
    L = []
    L.append(f'# {away} @ {home} — V1 Pregame Player Board')
    L.append('')
    L.append(f'**{a["label"]}.** {a["note"]}')
    L.append('')
    L.append(f'- Game `{board["game_id"]}`, kickoff **{f["kickoff_utc"]}**')
    L.append(f'- Forecast written at **{f["written_at"]}** '
             f'({f["lead_time_hours"]}h before kickoff)')
    L.append(f'- Model configuration **{board["model_configuration"]}**, '
             f'components applied: '
             f'{", ".join(board["component_manifest"]["applied"]) or "none"}'
             + (f'; not reached: '
                f'{", ".join(board["component_manifest"]["not_reached"])}'
                if board['component_manifest']['not_reached'] else ''))
    L.append(f'- Run `{board["run_id"]}`, {board["n_draws"]} draws, '
             f'draw digest `{board["draw_content_digest"]}`')
    L.append(f'- NFL-1 **{a["nfl1"]}** (`{a["code"]}`); promoted '
             f'`{a["promoted"]}`, prospective_eligible '
             f'`{a["prospective_eligible"]}`')
    L.append('')
    L.append('`*` = provisional layer (governed, but under a declared '
             'caveat). Metrics V1 does not model are listed at the end and '
             'are never estimated in their place.')
    L.append('')

    # ---- data freshness ------------------------------------------------
    L.append('## Data freshness')
    L.append('')
    L.append('| Source | Retrieved | Hours before kickoff |')
    L.append('|---|---|--:|')
    for s in f['sources']:
        L.append(f'| {s["source"]} | {s["retrieved_at"]} | '
                 f'{s["hours_before_kickoff"]} |')
    L.append('')
    if board.get('readiness'):
        L.append('| Team | Status confidence |')
        L.append('|---|---|')
        for t, r in sorted(board['readiness'].items()):
            L.append(f'| {t} | `{r.get("state")}` — {r.get("reason", "")[:90]} |')
        L.append('')

    # ---- positions -----------------------------------------------------
    by_pos = {}
    for r in board['players']:
        by_pos.setdefault(r['position'], []).append(r)
    for pos in M.POSITION_ORDER:
        L.append(f'## {TITLES[pos]}')
        L.append('')
        L.extend(player_table(by_pos.get(pos, []), pos, names))

    # ---- touchdowns ----------------------------------------------------
    L.append('## Touchdown probabilities')
    L.append('')
    L.append('_Anytime is the share of simulated games in which the player '
             'scored at all, summed within each draw — not a product of '
             'marginals, which would invent an independence the draws do not '
             'have. A passing touchdown is not a touchdown the passer '
             'scored and is listed separately._')
    L.append('')
    td = [r for r in board['players']
          if (r['touchdown'] or {}).get('anytime') is not None]
    td.sort(key=lambda r: -r['touchdown']['anytime'])
    if td:
        L.append('| Player | Pos | Anytime TD | 2+ TD | Components |')
        L.append('|---|---|--:|--:|---|')
        for r in td:
            t = r['touchdown']
            comp = ', '.join(f'{k.split("/")[-1]} {v:.0%}'
                             for k, v in sorted(t['components'].items()))
            L.append(f'| {_name(r, names)} | {r["position"]} | '
                     f'{t["anytime"]:.0%} | {t.get("two_plus", 0):.0%} | '
                     f'{comp} |')
    else:
        L.append('_No touchdown distribution was produced for this game._')
    L.append('')

    # ---- thresholds ----------------------------------------------------
    L.append('## Threshold probabilities')
    L.append('')
    L.append(f'_{board["threshold_disclaimer"]}_')
    L.append('')
    for pos, wanted in (
            ('QB', [('qb', 'pyds'), ('qb', 'ptd'), ('qb', 'int'),
                    ('qb', 'att'), ('qb', 'ryds')]),
            ('RB', [('rushing', 'carries'), ('receiving', 'receptions'),
                    ('receiving', 'receiving_yards')]),
            ('WR', [('receiving', 'receptions'),
                    ('receiving', 'receiving_yards')]),
            ('TE', [('receiving', 'receptions'),
                    ('receiving', 'receiving_yards')])):
        rows = by_pos.get(pos, [])[:6]
        blk = threshold_block(rows, pos, names, wanted)
        if blk:
            L.append(f'### {TITLES[pos]}')
            L.append('')
            L.extend(blk)

    # ---- confidence ----------------------------------------------------
    cb = board['confidence_board']
    L.append('## Highest-confidence projections')
    L.append('')
    L.append(f'_{cb["means"]}. {cb["no_market_feed"]}. Dimensions are '
             f'weighted equally — {cb["weights_note"]}._')
    L.append('')
    L.append('| Player | Pos | Score | Why |')
    L.append('|---|---|--:|---|')
    for r in cb['highest_confidence']:
        c = r['confidence']
        why = '; '.join(f'{k.replace("_", " ")}: {v}'
                        for k, v in list(c['reasons'].items())[:3])
        L.append(f'| {_name(r, names)} | {r["position"]} | '
                 f'{c["score"]:.2f} | {why} |')
    L.append('')
    L.append('## Widest-uncertainty projections')
    L.append('')
    L.append('_A wide distribution is not an error. For a rotational player '
             'it is the model correctly declining to be certain._')
    L.append('')
    L.append('| Player | Pos | Primary metric | Width | Score |')
    L.append('|---|---|---|---|--:|')
    for r in cb['widest_uncertainty']:
        c = r['confidence']
        L.append(f'| {_name(r, names)} | {r["position"]} | '
                 f'{c["primary_metric"]} | '
                 f'{c["reasons"]["distribution_width"]} | {c["score"]:.2f} |')
    L.append('')

    # ---- what is NOT modelled -------------------------------------------
    L.append('## Unavailable and provisional')
    L.append('')
    L.append('These are quantities a reader may expect and this model does '
             'not produce. They are named rather than estimated.')
    L.append('')
    for u in board['unavailable_metrics']:
        L.append(f'- **{u["label"]}** — `{u["code"]}`. {u["reason"]}')
    L.append('')
    prov = sorted({(m['label'], m['caveat'])
                   for r in board['players'] for m in r['metrics'].values()
                   if m['status'] == M.PROVISIONAL and m.get('caveat')})
    if prov:
        L.append('Provisional layers, shown with `*`:')
        L.append('')
        for lab, cav in prov:
            L.append(f'- **{lab}** — {cav}')
        L.append('')
    gov = board.get('layer_governance') or []
    if gov:
        L.append('Layer governance, as each layer declares it:')
        L.append('')
        L.append('| Stage | State | Declared spec / governance |')
        L.append('|---|---|---|')
        for g in gov:
            if not g['spec_version'] and not g['warnings']:
                continue
            note = g['spec_version']
            if g['warnings']:
                note += ' — ' + '; '.join(g['warnings'])
            L.append(f'| {g["stage"]} | {g["state"]} | {note} |')
        L.append('')
    missing = [r for r in board['players'] if not r['metrics']]
    L.append(f'_{len(missing)} player(s) on the slate carry no forecast '
             f'distribution at all._' if missing else
             '_Every player the engine covered carries at least one '
             'distribution._')
    L.append('')
    return '\n'.join(L)
