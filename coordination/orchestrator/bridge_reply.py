#!/usr/bin/env python3.12
"""Build the comment the bridge writes back to its issue. Prints JSON.

IT IS A SCRIPT, NOT A HEREDOC IN THE WORKFLOW. The first version of the
bridge workflow embedded this as inline Python inside a YAML block scalar and
the file would not parse, because a script line at column 0 ends the block.
Beyond that, code in a workflow cannot be tested; code here can.

IT RUNS ON EVERY OUTCOME, INCLUDING REFUSAL. A bridge that goes quiet when it
refuses cannot be told apart from one that is still thinking, and the
assistant reading the issue has no way to ask which it is. Silence is the
failure mode this whole project keeps paying for.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

REASON_FILE = 'gate_output.txt'
STATUS_FILE = 'bridge_status.md'


def build(env=None, root='.') -> dict:
    env = os.environ if env is None else env
    d = pathlib.Path(root)
    gate = env.get('GATE_OUTCOME', '')
    mode = env.get('MODE') or 'UNCLASSIFIED'

    reason = ''
    rp = d / REASON_FILE
    if rp.exists():
        reason = rp.read_text()[:2000]
    sp = d / STATUS_FILE
    contract = sp.read_text() if sp.exists() else ''

    if gate != 'success':
        human = ('**Bridge request refused.** Claude was not invoked and no '
                 'subscription usage was consumed.\n\n```\n'
                 + (reason or '(the gate produced no output, which is itself '
                              'a defect worth reporting)')
                 + '\n```')
    elif mode == 'ENGINEERING':
        human = ('**Handed to the governed engineering path.** The bridge '
                 'does not execute engineering work. It dispatched '
                 '`claude-engineering-dispatch.yml` for '
                 f'`{env.get("TASK_ID", "")}` (HTTP '
                 f'{env.get("HANDOFF_HTTP", "?")}). That workflow\'s '
                 'pre-flight re-derives authorization from committed state '
                 'and decides whether it may run; this dispatch does not '
                 'authorize anything.')
    else:
        conclusion = env.get('CLAUDE_CONCLUSION', '')
        human = ('**Answered.** Claude Code conclusion: '
                 f'`{conclusion or "(empty)"}`. An empty conclusion means '
                 'the Action produced no verdict, which is not the same as '
                 'success.')

    body = (human + '\n\n' + contract
            + f'\nrun: {env.get("GITHUB_RUN_ID", "")}\n')
    return {'body': body}


if __name__ == '__main__':
    json.dump(build(), sys.stdout)
    sys.stdout.write('\n')
