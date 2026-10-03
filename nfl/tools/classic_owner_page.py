#!/usr/bin/env python3.12
"""Render the owner's slate page from the frozen board, portfolio and upload-verification artifacts.

    python3.12 nfl/tools/classic_owner_page.py 2026W4 --out <path>.html

Presentation only. It reads the JSON the governed tools wrote and computes nothing that changes a
number: every figure on the page is copied from an artifact, and a missing artifact is shown as
missing, never filled in. The slate is called READY only when the board's readiness block has no
BLOCKED or STALE_OR_PENDING item and the upload file verified with zero violations.
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = _REPO / 'nfl/dfs/salaries'


def _load(slate_id, name):
    p = OUT_DIR / f'DK_{slate_id}_EARLY_{name}.json'
    return json.loads(p.read_text()) if p.exists() else None


def e(x):
    return html.escape('' if x is None else str(x))


def pct(x):
    return '' if x is None else f'{100 * x:.0f}%'


def _game_label(gid):
    parts = str(gid).split('_')
    return f'{parts[-2]} @ {parts[-1]}' if len(parts) >= 4 else str(gid)


def _top(d, k=8):
    return list(d.items())[:k]


def contest_card(c, verify):
    r = c['report']
    pol = c['policy']
    legal = c['FILLED'] and not c['violations']
    overl = r['overlap_distribution']
    n_pairs = sum(overl.values()) or 1
    mean_ov = sum(int(k) * v for k, v in overl.items()) / n_pairs
    max_ov = max((int(k) for k in overl), default=0)
    shared = None
    if verify:
        for k, v in (verify.get('cross_contest_identical_lineups') or {}).items():
            if k.startswith(f"{c['contest_id']}_in_"):
                shared = (shared or 0) + v['shared_lineups']
    qbs = ''.join(f'<li><span>{e(n)}</span><b>{pct(v)}</b></li>' for n, v in _top(r['qb_exposure'], 6))
    dsts = ''.join(f'<li><span>{e(n)}</span><b>{pct(v)}</b></li>' for n, v in _top(r['dst_exposure'], 4))
    plays = ''.join(f'<li><span>{e(n)} <i>{e(v["pos"])}</i></span><b>{pct(v["overall"])}</b></li>'
                    for n, v in _top(r['player_exposure'], 10))
    games = ''.join(f'<li><span>{e(_game_label(g))}</span><b>{pct(v)}</b></li>' for g, v in _top(r['game_exposure'], 8))
    stk = r['stack_table']
    qb_stack = {k: v for k, v in stk.items() if k.startswith('QB+')}
    bb = r['bring_back_table']
    sal = r['salary_used']
    return f'''
<article class="contest">
  <header>
    <div>
      <h3>{e(c['contest_name'])}</h3>
      <p class="meta">Contest {e(c['contest_id'])} · {e(c['entry_fee'])} · profile {e(c['profile'])}</p>
    </div>
    <span class="pill {'ok' if legal else 'bad'}">{c['n_filled']}/{c['n_entries']} {'legal' if legal else 'NOT LEGAL'}</span>
  </header>
  <dl class="facts">
    <div><dt>Distinct lineups</dt><dd>{r['n_unique']}</dd></div>
    <div><dt>Mean lineup overlap</dt><dd>{mean_ov:.1f} <small>of 9 (max {max_ov})</small></dd></div>
    <div><dt>Salary used</dt><dd>{sal['min']:,}–{sal['max']:,} <small>median {sal['median']:,.0f}</small></dd></div>
    <div><dt>Worlds where best entry clears the bar</dt><dd>{pct(r['p_any_entry_clears_bar'])}</dd></div>
    <div><dt>Lineups also in a larger contest</dt><dd>{'' if shared is None else shared}</dd></div>
    <div><dt>Candidates / pool</dt><dd>{c['n_candidates']} <small>from {c['pool_size']} players</small></dd></div>
  </dl>
  <p class="policy">Declared policy, not measured: player cap {pct(pol['exposure_cap'])}, QB cap {pct(pol['qb_exposure_cap'])},
     DST cap {pct(pol['dst_exposure_cap'])}, at most {pol['max_shared']} players shared by any two lineups,
     bar at the top {pct(pol['q'])} of candidate scores in each world.</p>
  <div class="cols">
    <section><h4>Quarterbacks</h4><ul class="bars">{qbs}</ul></section>
    <section><h4>Most-used players</h4><ul class="bars">{plays}</ul></section>
    <section><h4>Games</h4><ul class="bars">{games}</ul></section>
    <section><h4>Stacks and defenses</h4>
      <ul class="bars">{''.join(f'<li><span>{e(k.replace("QB+", "QB + ") + " pass catchers")}</span><b>{pct(v)}</b></li>' for k, v in qb_stack.items())}
      {''.join(f'<li><span>{e(k.replace("bring_back_", "bring-back "))}</span><b>{pct(v)}</b></li>' for k, v in bb.items())}</ul>
      <ul class="bars">{dsts}</ul></section>
  </div>
</article>'''


def _n1(v):
    return '' if v is None else f'{v:.1f}'


def _li(xs, empty='none'):
    xs = [x for x in xs if x]
    return ''.join(f'<li>{e(x)}</li>' for x in xs) if xs else f'<li class="fine">{e(empty)}</li>'


def team_block(t):
    q = t.get('qb_ecosystem') or {}
    env = t['environment']
    tree = ''.join(
        f"<tr><td>{e(x['name'])}</td><td>{e(x['pos'])}</td><td class=\"n\">{x['proj_targets'] or 0:.1f}</td>"
        f"<td class=\"n\">{pct(x['share_of_club_targets'])}</td><td class=\"n\">{_n1(x['rz_targets_proj'])}</td>"
        f"<td class=\"n\">{e(x['deep_targets_2026'])}</td>"
        f"<td class=\"n\">{'' if x['targets_if_trailing_by_8+'] is None else x['targets_if_trailing_by_8+']}</td>"
        f"<td class=\"n\">{'' if x['targets_if_leading_by_8+'] is None else x['targets_if_leading_by_8+']}</td></tr>"
        for x in (q.get('target_tree') or [])[:7])
    rb = ''.join(
        f"<tr><td>{e(b['name'])}</td><td class=\"n\">{pct(b['carry_share_proj'])}</td><td class=\"n\">{pct(b['target_share_of_rb_proj'])}</td>"
        f"<td class=\"n\">{b['early_down_carries_2026']}</td><td class=\"n\">{b['third_down_targets_2026']}</td>"
        f"<td class=\"n\">{b['gl_carries_2026']}</td><td>{e(', '.join(b['roles']) or '')}</td></tr>"
        for b in (t['rb_ecosystem']['backs'] or [])[:4])
    ol = ', '.join(f"{x['slot']} {x.get('starter')}" + (f" ({x['report_status']}" + (f"; next {x['next_on_chart']}" if x.get('next_on_chart') else '') + ')'
                   if x.get('report_status') not in (None, 'NOT_ON_REPORT', 'NONE_LISTED') else '')
                   for x in t['offensive_line']['starters'])
    opp = t['opponent_layer']
    oc = opp['OBSERVED_CONTEXT_2026']
    dout = ', '.join(f"{x['slot']} {x['player']}" for x in opp['defenders_out']) or 'none on the report'
    cas = [f"{c['player']} ({c['position']}) out" + (
        f": vacates {c['vacated_per_game_2026']['targets']} targets, {c['vacated_per_game_2026']['carries']} carries, "
        f"{c['vacated_per_game_2026']['pass_att']} attempts per game; projection gives more to "
        + ', '.join(w['name'] for w in c['who_the_projection_gives_more_to'][:3]) if c.get('vacated_per_game_2026') else ': no modelled effect')
        for c in t['injury_cascades']]
    acc = t['accounting']
    yc = acc['yards_closure_DIAGNOSTIC_NOT_A_GATE']
    return f"""
    <div class="team">
      <h4>{e(t['club'])} offence <span class="fine">expected {env['expected_points']} pts · {env['proj_pass_attempts']} pass att · {env['proj_rush_attempts']} rush att (2026: {env['measured_2026_per_game']['pass_att']} / {env['measured_2026_per_game']['carries']})</span></h4>
      <p class="fine"><b>Depth chart:</b> {e('; '.join(f"{k} " + ', '.join(v[:3]) for k, v in t['depth_tree_declared'].items()))}</p>
      <p class="fine"><b>QB:</b> {e(q.get('quarterback'))} · {e(q.get('his_pass_attempts'))} attempts · projected {e((q.get('efficiency_projected') or {}).get('yards_per_attempt'))} yds/att (2026 {e((q.get('efficiency_2026') or {}).get('yards_per_attempt'))}) · club attempts if trailing by 8+ {e(q.get('club_pass_attempts_if_trailing_by_8+'))}, if leading {e(q.get('club_pass_attempts_if_leading_by_8+'))}</p>
      <div class="scroll"><table><thead><tr><th>Target tree</th><th>Pos</th><th>Targets</th><th>Share</th><th>RZ tgt</th><th>Deep 2026</th><th>If trailing</th><th>If leading</th></tr></thead><tbody>{tree}</tbody></table></div>
      <div class="scroll"><table><thead><tr><th>RB room</th><th>Carry share</th><th>RB target share</th><th>Early-down car. 2026</th><th>3rd-down tgt 2026</th><th>Goal-line car. 2026</th><th>Measured role</th></tr></thead><tbody>{rb}</tbody></table></div>
      <p class="fine"><b>Offensive line:</b> {e(ol)}. No modelled line effect.</p>
      <p class="fine"><b>Against {e(opp['opponent'])} (observed, not modelled):</b> {oc['pass_att_faced_pg']} pass att faced/g, sack rate {pct(oc['sack_rate'])}, explosive pass {pct(oc['explosive_pass_rate_allowed'])}, explosive run {pct(oc['explosive_run_rate_allowed'])}; defenders out: {e(dout)}</p>
      <ul class="fine">{_li(cas, 'no players reported out')}</ul>
      <p class="fine"><b>Accounting:</b> attempts {acc['pass_attempts']['state']}, targets {acc['targets']['state']}, carries {acc['carries']['state']}, receiving TD = passing TD {acc['receiving_td_eq_passing_td']['state']}; yards closure (diagnostic) receivers {yc['receivers_rec_yards']} vs QB {yc['qbs_pass_yards']}.</p>
    </div>"""


def research_section(book):
    if not book:
        return '<p class="missing">No research book for these inputs.</p>'
    out = []
    for gid, g in sorted(book['games'].items(), key=lambda kv: -(kv[1]['summary']['GAME_ENVIRONMENT']['football_total'] or 0)):
        sm = g['summary']
        env = sm['GAME_ENVIRONMENT']
        stories = ''.join(f"<li><span>{e(x['story'])}</span><b>{pct(x['share_of_worlds'])}</b></li>" for x in g['game_stories']['stories'][:5])
        corr = '; '.join(f"{c}: " + ', '.join(f"{x['with']} r={x['r']}" for x in v[:3]) for c, v in sm['DFS_CORRELATIONS'].items())
        out.append(f"""
  <details class="game">
    <summary><b>{e(g['away'])} @ {e(g['home'])}</b> <span class="fine">our total {env['football_total']}, home margin {env['home_margin']:+.1f}, simulated 10th–90th {env['simulated_total_p10_p50_p90'][0]}–{env['simulated_total_p10_p50_p90'][2]}</span></summary>
    <div class="cols">
      <section><h4>How the worlds play out</h4><ul class="bars">{stories}</ul></section>
      <section><h4>Key role changes</h4><ul class="fine">{_li(sm['KEY_ROLE_CHANGES'])}</ul></section>
      <section><h4>Low-confidence</h4><ul class="fine">{_li(sm['LOW_CONFIDENCE'])}</ul></section>
      <section><h4>Best understood</h4><ul class="fine">{_li(sm['BEST_UNDERSTOOD'])}</ul><p class="fine">QB correlations: {e(corr)}</p></section>
    </div>
    {''.join(team_block(g['teams'][c]) for c in (g['away'], g['home']))}
  </details>""")
    return ''.join(out)


def reasoning_section(r):
    if not r:
        return '<p class="missing">No exposure reasoning (no research book or portfolio for these inputs).</p>'
    rows = ''.join(
        f"<tr><td>{e(x['player'])}</td><td>{e(x['team'])}</td><td>{e(x['position'])}</td>"
        f"<td class=\"n\">{pct(x['exposure'].get('MAX150'))}</td><td class=\"n\">{pct(x['exposure'].get('MAX20'))}</td>"
        f"<td class=\"n\">{pct(x['exposure'].get('MAX3'))}</td><td>{e('; '.join(x['why']))}</td><td>{e('; '.join(x['risk']))}</td></tr>"
        for x in r['players'])
    shapes = ''.join(f"<section><h4>{e(k)}</h4><ul class=\"bars\">" + ''.join(
        f"<li><span>{e(x['shape'])}</span><b>{pct(x['share'])}</b></li>" for x in v) + '</ul></section>'
        for k, v in r['stack_shapes'].items())
    un = r.get('UNEXPLAINED') or []
    return f"""
    <div class="scroll" style="max-height:60vh"><table><thead><tr><th>Player</th><th>Team</th><th>Pos</th><th>150-max</th><th>20-max</th><th>3-entry</th><th>Why he is in</th><th>Risk</th></tr></thead><tbody>{rows}</tbody></table></div>
    <p class="{'missing' if un else 'fine'}">{'Unexplained exposures (investigate): ' + e(', '.join(x['player'] for x in un)) if un else 'Every player at 10%+ exposure in any contest has a football reason.'}</p>
    <h3>Stack shapes built</h3><p class="fine">WR1/TE1/RB1 are ranks by projected targets inside the club.</p><div class="cols">{shapes}</div>"""


def build(slate_id):
    b = _load(slate_id, 'OWNER_BOARD')
    if b is None:
        raise SystemExit(f'DK_{slate_id}_EARLY_OWNER_BOARD.json missing: build the board first')
    port = _load(slate_id, 'PORTFOLIOS')
    ver = _load(slate_id, 'UPLOAD_VERIFY')
    ch = _load(slate_id, 'CHANGES')
    book = _load(slate_id, 'RESEARCH_BOOK')
    props = _load(slate_id, 'PROP_DIAGNOSTIC')
    seal = _load(slate_id, 'SEAL')
    rd = b['readiness']
    verified = bool(ver and ver.get('state') == 'PASS')
    ready = verified and not rd.get('BLOCKED') and not rd.get('STALE_OR_PENDING')
    status = 'READY' if ready else 'NOT READY TO SUBMIT'
    why = [] if ready else (rd.get('BLOCKED', []) + rd.get('STALE_OR_PENDING', [])
                            + ([] if verified else ['upload file not verified']))
    contests = ''.join(contest_card(c, ver) for c in (port or {}).get('contests', [])) or \
        '<p class="missing">No portfolio artifact for this slate.</p>'
    games = ''.join(f'''<tr><td>{e(g['away'])} @ {e(g['home'])}</td><td class="n">{g['football_total']:.1f}</td>
      <td class="n">{g['away_expected']:.1f}</td><td class="n">{g['home_expected']:.1f}</td>
      <td class="n">{g['home_margin']:+.1f}</td>
      <td class="n">{g['away_volume']['proj_pass_attempts']:.0f} / {g['home_volume']['proj_pass_attempts']:.0f}</td>
      <td class="n">{g['away_volume']['proj_rush_attempts']:.0f} / {g['home_volume']['proj_rush_attempts']:.0f}</td>
      <td>{e(', '.join(x.rsplit(' p95', 1)[0] for x in g['best_ceiling_players'][:3]))}</td>
      <td>{e(', '.join(g['injury_sensitivity']) or '—')}</td></tr>''' for g in
                    sorted(b['games'], key=lambda g: -g['football_total']))
    keep = ('player', 'team', 'opp', 'pos', 'salary', 'classification', 'role', 'starter_state', 'designation',
            'sim_mean', 'floor_p10', 'p90', 'ceiling_p99', 'value_per_1k', 'exp_150max', 'exp_20max',
            'exp_3entry', 'fc_proj', 'fc_diff', 'key_reason', 'key_risk')
    players = [{k: p.get(k) for k in keep} for p in b['players'] if p['classification'] != 'non-playable']
    gaps = ''.join(f'''<tr><td>{e(g['player'])}</td><td>{e(g['team'])}</td><td>{e(g['pos'])}</td>
      <td class="n">{g['ours_sim_mean']:.1f}</td><td class="n">{g['fc_proj']:.1f}</td>
      <td class="n {'up' if g['diff'] > 0 else 'dn'}">{g['diff']:+.1f}</td><td>{e(g['our_role'])}</td>
      <td>{e(g['our_key_reason'])}</td></tr>''' for g in sorted(b.get('fc_comparison', []),
                                                                key=lambda g: -abs(g['diff']))[:30])
    changes = ''.join(f'<li><b>{e(x["what"])}</b> {e(x["detail"])}</li>' for x in (ch or {}).get('changes', [])) \
        or '<li class="missing">No change log artifact.</li>'
    moved = ''.join(f'''<tr><td>{e(m['name'])}</td><td>{e(m['team'])}</td><td>{e(m['pos'])}</td>
      <td>{e(m['band_before'])} → {e(m['band_after'])}</td><td class="n">{m['before']:.1f}</td>
      <td class="n">{m['after']:.1f}</td><td class="n {'up' if m['delta'] > 0 else 'dn'}">{m['delta']:+.1f}</td></tr>'''
                    for m in (ch or {}).get('largest_moves', []))
    simmoves = ''.join(f'''<tr><td>{e(m['name'])}</td><td>{e(m['team'])}</td><td>{e(m['pos'])}</td>
      <td class="n">{m['projection']:.1f}</td><td class="n">{m['sim_before']:.1f}</td><td class="n">{m['sim_after']:.1f}</td></tr>'''
                       for m in (ch or {}).get('simulation_moves', []))
    lst = lambda xs: ''.join(f'<li>{e(x)}</li>' for x in xs)  # noqa: E731
    cc = rd.get('classification_counts', {})
    acc_state = (book or {}).get('ACCOUNTING', {}).get('state', 'NOT BUILT')
    if props and props.get('n_rows'):
        prop_html = f"<p>{props['n_rows']} comparable Hard Rock rows, {props['n_attention']} flagged for attention. See DK_{e(slate_id)}_EARLY_PROP_DIAGNOSTIC.json.</p>"
    else:
        prop_html = ('<p class="missing">No Hard Rock board for these eight games is held yet. It was requested from the '
                     'networked agent. Our prop distributions are frozen in the research book and the stored worlds '
                     f"(sealed {e((seal or {}).get('written_at', '')[:16])}Z); any price captured before that time is refused.</p>")
    return TEMPLATE.format(
        research=research_section(book), reasoning=reasoning_section(b.get('dfs_reasoning')),
        accounting=e(acc_state), props=prop_html,
        status=status, status_cls='ok' if ready else 'bad', why=lst(why), built=e(b['built_at_utc'][:16] + 'Z'),
        validation=e(rd['VALIDATION_STATE']), contests=contests, games=games, gaps=gaps,
        n_gaps=len(b.get('fc_comparison', [])), changes=changes, moved=moved, simmoves=simmoves,
        current=lst(rd['CURRENT']), pending=lst(rd['STALE_OR_PENDING']), unresolved=lst(rd['UNRESOLVED']),
        notmod=lst(rd['NOT_MODELLED']), counts=e(', '.join(f'{k} {v}' for k, v in cc.items())),
        verify=e(f"{ver['state']}[{ver['code']}] {ver['detail']}" if ver else 'not run'),
        upload_sha=e((ver or {}).get('upload_sha256', '')[:16]),
        players=json.dumps(players, separators=(',', ':')).replace('</', '<\\/'),
        hard_rock=e(b['players'][0].get('hard_rock', '')), slate=e(slate_id))


TEMPLATE = '''<title>Week 4 Early Slate Desk</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: one desk, read top to bottom - verdict, contests, games, players, then what changed and what is missing. */
:root {{
  --bg: #f3f5f2; --panel: #ffffff; --ink: #16211b; --muted: #5d6b63; --line: #d8dfd9;
  --accent: #1d6b45; --ok: #1d6b45; --bad: #a3342b; --warn: #8a5a00; --bar: #cfe3d6;
  --display: "Barlow Condensed", "Arial Narrow", sans-serif; --body: "Source Sans 3", "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #0f1512; --panel: #17201b; --ink: #e3ebe5; --muted: #98a89e; --line: #2b3931;
  --accent: #6fcf9a; --ok: #6fcf9a; --bad: #f08a7e; --warn: #e3b341; --bar: #24412f; color-scheme: dark }} }}
:root[data-theme="dark"] {{
  --bg: #0f1512; --panel: #17201b; --ink: #e3ebe5; --muted: #98a89e; --line: #2b3931;
  --accent: #6fcf9a; --ok: #6fcf9a; --bad: #f08a7e; --warn: #e3b341; --bar: #24412f; color-scheme: dark }}
body {{ background: var(--bg); color: var(--ink); font: 15px/1.5 var(--body); }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding-inline: 16px; padding-block: 24px 64px; display: grid; gap: 28px; }}
h1, h2, h3, h4 {{ font-family: var(--display); letter-spacing: .01em; text-wrap: balance; margin: 0; }}
h1 {{ font-size: 2.4rem; font-weight: 700; line-height: 1.05; }}
h2 {{ font-size: 1.6rem; font-weight: 600; border-bottom: 2px solid var(--ink); padding-bottom: 4px; }}
h3 {{ font-size: 1.25rem; font-weight: 600; }}
h4 {{ font-size: .95rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 600; }}
.meta, small, .policy {{ color: var(--muted); }}
.meta {{ margin: 2px 0 0; font-size: .9rem; }}
section.block {{ display: grid; gap: 14px; min-width: 0; }}
.verdict {{ display: grid; gap: 10px; padding: 18px; background: var(--panel); border: 1px solid var(--line); border-left: 6px solid var(--bad); }}
.verdict.ok {{ border-left-color: var(--ok); }}
.verdict .status {{ font-family: var(--display); font-size: 1.9rem; font-weight: 700; color: var(--bad); }}
.verdict.ok .status {{ color: var(--ok); }}
.verdict ul {{ margin: 0; padding-left: 18px; }}
.pill {{ font: 600 .8rem var(--mono); padding: 3px 9px; border-radius: 99px; border: 1px solid currentColor; white-space: nowrap; }}
.pill.ok {{ color: var(--ok); }} .pill.bad {{ color: var(--bad); }}
.contests {{ display: grid; gap: 18px; }}
.contest {{ background: var(--panel); border: 1px solid var(--line); padding: 16px; display: grid; gap: 14px; min-width: 0; }}
.contest > header {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; flex-wrap: wrap; }}
.facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px 18px; margin: 0; }}
.facts dt {{ font-size: .78rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }}
.facts dd {{ margin: 0; font: 600 1.15rem var(--mono); font-variant-numeric: tabular-nums; }}
.policy {{ margin: 0; font-size: .88rem; }}
.cols {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; }}
.cols section {{ display: grid; gap: 6px; align-content: start; min-width: 0; }}
ul.bars {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 3px; }}
ul.bars li {{ display: flex; justify-content: space-between; gap: 8px; font-size: .9rem; padding: 2px 6px; background: linear-gradient(90deg, var(--bar) var(--w, 0%), transparent 0); }}
ul.bars b {{ font: 600 .85rem var(--mono); font-variant-numeric: tabular-nums; }}
ul.bars i {{ color: var(--muted); font-style: normal; font-size: .8rem; }}
.scroll {{ overflow-x: auto; border: 1px solid var(--line); background: var(--panel); }}
table {{ border-collapse: collapse; width: 100%; font-size: .88rem; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
th {{ font-family: var(--display); font-weight: 600; font-size: .95rem; letter-spacing: .03em; position: sticky; top: 0; background: var(--panel); cursor: default; white-space: nowrap; }}
th[data-k] {{ cursor: pointer; }} th[data-k]:hover {{ color: var(--accent); }}
td.n {{ font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }}
td.up {{ color: var(--ok); }} td.dn {{ color: var(--bad); }}
.controls {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
.controls label {{ font-size: .85rem; color: var(--muted); display: flex; gap: 6px; align-items: center; }}
select, input {{ font: inherit; padding: 4px 8px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); }}
select:focus-visible, input:focus-visible, th:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
.grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
.grid2 > div {{ background: var(--panel); border: 1px solid var(--line); padding: 14px; min-width: 0; }}
.grid2 ul, .changes {{ margin: 6px 0 0; padding-left: 18px; }}
.changes li {{ margin-bottom: 6px; }}
.missing {{ color: var(--warn); }}
details.game {{ background: var(--panel); border: 1px solid var(--line); padding: 10px 14px; }}
details.game > summary {{ cursor: pointer; font-size: 1rem; }}
details.game[open] {{ display: grid; gap: 12px; }}
.team {{ display: grid; gap: 6px; border-top: 1px solid var(--line); padding-top: 10px; min-width: 0; }}
.team h4 {{ text-transform: none; letter-spacing: 0; color: var(--ink); font-size: 1.1rem; }}
.team p {{ margin: 0; }}
.fine {{ font-size: .85rem; color: var(--muted); }}
code {{ font-family: var(--mono); font-size: .85em; word-break: break-all; }}
.cls-viable {{ color: var(--ok); }} .cls-inactive, .cls-unresolved {{ color: var(--bad); }} .cls-thin, .cls-role-dependent {{ color: var(--warn); }}
</style>
<div class="wrap">
  <header style="display:grid;gap:6px">
    <p class="meta">DraftKings Classic · Early Only · Sunday 4 October 2026, 1:00 PM ET · 8 games · slate {slate}</p>
    <h1>Week 4 Early Slate Desk</h1>
    <p class="meta">Built {built} from the frozen football world. Our projections use football inputs only; no sportsbook line, FantasyCruncher number or DraftKings average went into them.</p>
  </header>

  <div class="verdict {status_cls}">
    <div class="status">{status}</div>
    <ul>{why}</ul>
    <p class="fine">{validation}</p>
  </div>

  <section class="block">
    <h2>Contest portfolios</h2>
    <p class="fine">Each contest was optimised as its own portfolio from the same 2,000 simulated worlds. The 20-entry set was not taken from the 150-entry set. Ownership data does not exist for this slate, so duplication risk is not modelled. Upload check: {verify} (file sha256 {upload_sha}…).</p>
    <div class="contests">{contests}</div>
  </section>

  <section class="block">
    <h2>Why each player is in</h2>
    <p class="fine">Every reason comes from the research book or the joint simulation: role, volume, injury context, salary efficiency, ceiling, stack correlation.</p>
    {reasoning}
  </section>

  <section class="block">
    <h2>Game research book</h2>
    <p class="fine">Team accounting (attempts, targets, carries, touchdowns reconcile to club totals): <b>{accounting}</b>. Lineups are refused unless it passes. Routes, alignment, personnel and pressure are not in any capture and are shown as unavailable, never as zero. Opponent and offensive-line information is observed context; neither changes a projected number.</p>
    {research}
  </section>

  <section class="block">
    <h2>Hard Rock props</h2>
    {props}
  </section>

  <section class="block">
    <h2>Game environments</h2>
    <p class="fine">Our football-only numbers. Hard Rock comparison: {hard_rock}</p>
    <div class="scroll"><table>
      <thead><tr><th>Game</th><th>Our total</th><th>Away pts</th><th>Home pts</th><th>Home margin</th><th>Pass att A / H</th><th>Rush att A / H</th><th>Top ceilings</th><th>Injury exposure</th></tr></thead>
      <tbody>{games}</tbody></table></div>
  </section>

  <section class="block">
    <h2>Player board</h2>
    <div class="controls">
      <label for="f-pos">Position <select id="f-pos"><option value="">All</option><option>QB</option><option>RB</option><option>WR</option><option>TE</option><option>DST</option></select></label>
      <label for="f-cls">Class <select id="f-cls"><option value="">All playable</option><option>viable</option><option>thin</option><option>role-dependent</option><option>unresolved</option><option>inactive</option></select></label>
      <label for="f-q">Search <input id="f-q" type="search" placeholder="name or team"></label>
      <span class="fine" id="f-n"></span>
    </div>
    <p class="fine">Counts: {counts}. Click a column to sort. FC columns are an outside opinion shown for comparison only; nothing on this page was moved toward them.</p>
    <div class="scroll" style="max-height:70vh"><table id="pb"><thead><tr>
      <th data-k="player">Player</th><th data-k="team">Team</th><th data-k="pos">Pos</th><th data-k="salary">Salary</th>
      <th data-k="classification">Class</th><th data-k="role">Role</th><th data-k="sim_mean">Ours</th>
      <th data-k="floor_p10">p10</th><th data-k="p90">p90</th><th data-k="ceiling_p99">p99</th><th data-k="value_per_1k">Pts/$1k</th>
      <th data-k="exp_150max">150-max</th><th data-k="exp_20max">20-max</th><th data-k="exp_3entry">3-entry</th>
      <th data-k="fc_proj">FC</th><th data-k="fc_diff">Ours−FC</th><th>Why / risk</th></tr></thead><tbody></tbody></table></div>
  </section>

  <section class="block">
    <h2>Where we disagree with FantasyCruncher</h2>
    <p class="fine">{n_gaps} material gaps (at least 3 points, or 30% on projections of 8+). Largest 30 shown. A gap is a reason to look again at our inputs, never a correction.</p>
    <div class="scroll"><table><thead><tr><th>Player</th><th>Team</th><th>Pos</th><th>Ours</th><th>FC</th><th>Gap</th><th>Our role</th><th>Our reason</th></tr></thead><tbody>{gaps}</tbody></table></div>
  </section>

  <section class="block">
    <h2>What changed today</h2>
    <ul class="changes">{changes}</ul>
    <div class="scroll"><table><thead><tr><th>Player</th><th>Team</th><th>Pos</th><th>Role band</th><th>Before</th><th>After</th><th>Change</th></tr></thead><tbody>{moved}</tbody></table></div>
    <p class="fine">Depth-rule moves above are projection changes. Below, the simulated mean before and after the efficiency step; the projection itself did not change.</p>
    <div class="scroll"><table><thead><tr><th>Player</th><th>Team</th><th>Pos</th><th>Our projection</th><th>Simulated before</th><th>Simulated after</th></tr></thead><tbody>{simmoves}</tbody></table></div>
  </section>

  <section class="block">
    <h2>Evidence status</h2>
    <div class="grid2">
      <div><h4>Current</h4><ul>{current}</ul></div>
      <div><h4>Pending before lock</h4><ul>{pending}</ul></div>
      <div><h4>Unresolved</h4><ul>{unresolved}</ul></div>
      <div><h4>Not modelled</h4><ul>{notmod}</ul></div>
    </div>
    <p class="fine">Nothing here was uploaded or entered. Your DraftKings entries file was not modified; the lineups are in a new upload-format file for you to review.</p>
  </section>
</div>
<script>
const P = {players};
const tb = document.querySelector('#pb tbody'), fp = document.getElementById('f-pos'), fc = document.getElementById('f-cls'), fq = document.getElementById('f-q'), fn = document.getElementById('f-n');
let sortK = 'sim_mean', dir = -1;
const pc = v => v == null ? '' : Math.round(v * 100) + '%';
const nm = (v, d = 1) => v == null ? '' : Number(v).toFixed(d);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({{'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}})[c]);
function draw() {{
  const q = fq.value.trim().toLowerCase();
  const rows = P.filter(p => (!fp.value || p.pos === fp.value) && (!fc.value || p.classification === fc.value)
    && (!q || (p.player + ' ' + p.team).toLowerCase().includes(q)));
  rows.sort((a, b) => {{ const x = a[sortK], y = b[sortK]; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * dir; }});
  fn.textContent = rows.length + ' players';
  tb.innerHTML = rows.map(p => `<tr><td>${{esc(p.player)}}</td><td>${{esc(p.team)}} <span class="fine">v ${{esc(p.opp)}}</span></td><td>${{esc(p.pos)}}</td>
    <td class="n">${{p.salary.toLocaleString()}}</td><td class="cls-${{esc(p.classification)}}">${{esc(p.classification)}}${{p.designation ? ' · ' + esc(p.designation) : ''}}</td>
    <td>${{esc(p.role)}}</td><td class="n">${{nm(p.sim_mean)}}</td><td class="n">${{nm(p.floor_p10)}}</td><td class="n">${{nm(p.p90)}}</td>
    <td class="n">${{nm(p.ceiling_p99)}}</td><td class="n">${{nm(p.value_per_1k, 2)}}</td><td class="n">${{pc(p.exp_150max)}}</td>
    <td class="n">${{pc(p.exp_20max)}}</td><td class="n">${{pc(p.exp_3entry)}}</td><td class="n">${{nm(p.fc_proj)}}</td>
    <td class="n ${{p.fc_diff > 0 ? 'up' : p.fc_diff < 0 ? 'dn' : ''}}">${{p.fc_diff == null ? '' : (p.fc_diff > 0 ? '+' : '') + nm(p.fc_diff)}}</td>
    <td>${{esc(p.key_reason)}}${{p.key_risk && p.key_risk !== 'none named' ? '<br><span class="fine">Risk: ' + esc(p.key_risk) + '</span>' : ''}}</td></tr>`).join('');
}}
document.querySelectorAll('#pb th[data-k]').forEach(th => {{ th.tabIndex = 0; const go = () => {{ const k = th.dataset.k; dir = sortK === k ? -dir : -1; sortK = k; draw(); }}; th.addEventListener('click', go); th.addEventListener('keydown', ev => {{ if (ev.key === 'Enter') go(); }}); }});
[fp, fc].forEach(el => el.addEventListener('change', draw)); fq.addEventListener('input', draw);
document.querySelectorAll('ul.bars li').forEach(li => {{ const t = li.querySelector('b'); const v = parseFloat(t && t.textContent); if (!isNaN(v)) li.style.setProperty('--w', Math.min(v, 100) + '%'); }});
draw();
</script>
'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    pathlib.Path(a.out).write_text(build(a.slate_id))
    print(f'wrote {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
