#!/usr/bin/env python3.12
"""The transport to the three providers, and the mock that stands in for it.

WHY urllib AND NOT THE VENDOR SDKS. A GitHub Actions job that has to `pip
install openai anthropic` before it can read a queue is a job with three more
ways to fail and a supply chain three packages wide, for the sake of a POST
this module does in forty lines. Nothing here needs streaming, retries with
jitter, or tool-calling plumbing. `pip install` is not in the workflow at all.

THE ONE RULE THIS FILE EXISTS TO ENFORCE

    AN ABSENT RESPONSE IS NEVER A SUCCESSFUL ONE.

Timeout, HTTP error, empty body, unparseable JSON, a body with no text, a
refusal from the model, a response that does not match the schema the caller
asked for -- every one of those returns `WorkerResult(ok=False)` with a
distinct code. There is deliberately NO branch in this module that can produce
`ok=True` without a parsed body in hand. That is the defect class the owner's
briefing calls the most expensive in the project's history, and it is worth
the repetition.

MOCK MODE IS A SEPARATE PROVIDER, NOT A FLAG ON THE REAL ONE. `MOCK_PROVIDER`
reads a fixture from `mocks/` and returns it through the same `WorkerResult`
shape. It cannot be reached by accident -- `AUTONOMY_MODE` must say `MOCK` --
and, just as importantly, a missing API key never falls back to it. A mock
that stands in for a real call the operator believed they were making is a
fabricated result wearing a real one's clothes.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.error
import urllib.request

import pathlib as _pl, sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import contracts as C

HERE = pathlib.Path(__file__).resolve().parent
MOCKS = HERE / 'mocks'

MODE_MOCK = 'MOCK'
MODE_LIVE = 'LIVE'

ENDPOINTS = {
    'openai': 'https://api.openai.com/v1/chat/completions',
    'anthropic': 'https://api.anthropic.com/v1/messages',
    'perplexity': 'https://api.perplexity.ai/chat/completions',
}
SECRET_ENV = {
    'openai': 'OPENAI_API_KEY',
    'anthropic': 'ANTHROPIC_API_KEY',
    'perplexity': 'PERPLEXITY_API_KEY',
}


def mode(env=None) -> str:
    """LIVE only when asked for by name. Anything else is MOCK.

    The default is the cheap mode. Forgetting to set the variable costs
    nothing; the expensive mode has to be requested.
    """
    env = env if env is not None else os.environ
    return MODE_LIVE if (env.get('AUTONOMY_MODE') or '').upper() == 'LIVE' \
        else MODE_MOCK


# ------------------------------------------------------------ the wire
def _post(url, headers, body, timeout) -> tuple:
    """(status, bytes) or raises. No retry here -- policy owns retries."""
    req = urllib.request.Request(
        url, data=json.dumps(body).encode('utf-8'), method='POST',
        headers={'Content-Type': 'application/json', **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def _request_body(provider, model_cfg, system, user):
    """Each provider's shape, built here so no caller has to know it."""
    model = model_cfg['model']
    max_out = model_cfg.get('max_output_tokens', 8000)
    temp = model_cfg.get('temperature', 0)
    if provider == 'anthropic':
        return {'model': model, 'max_tokens': max_out, 'temperature': temp,
                'system': system,
                'messages': [{'role': 'user', 'content': user}]}
    # openai and perplexity are both chat/completions shaped.
    return {'model': model, 'max_tokens': max_out, 'temperature': temp,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': user}]}


def _headers(provider, key):
    if provider == 'anthropic':
        return {'x-api-key': key, 'anthropic-version': '2023-06-01'}
    return {'Authorization': f'Bearer {key}'}


def _extract_text(provider, payload) -> str:
    """The assistant's text, or '' -- and '' is treated as a FAILURE above."""
    try:
        if provider == 'anthropic':
            parts = payload.get('content') or []
            return ''.join(p.get('text', '') for p in parts
                           if isinstance(p, dict))
        ch = (payload.get('choices') or [{}])[0]
        return ((ch.get('message') or {}).get('content') or '')
    except (AttributeError, IndexError, TypeError):
        return ''


def _usage(provider, payload) -> dict:
    u = payload.get('usage') or {}
    if provider == 'anthropic':
        return {'input_tokens': u.get('input_tokens', 0),
                'output_tokens': u.get('output_tokens', 0),
                'total_tokens': (u.get('input_tokens', 0)
                                 + u.get('output_tokens', 0))}
    return {'input_tokens': u.get('prompt_tokens', 0),
            'output_tokens': u.get('completion_tokens', 0),
            'total_tokens': u.get('total_tokens', 0)}


# --------------------------------------------------------------- mocks
def _mock_path(worker, task_id) -> pathlib.Path:
    """A per-task fixture if one exists, else the worker's default."""
    specific = MOCKS / f'{worker.value.lower()}.{task_id}.json'
    return specific if specific.exists() \
        else MOCKS / f'{worker.value.lower()}.default.json'


def _mock(call, worker, task_id) -> C.WorkerResult:
    p = _mock_path(worker, task_id)
    if not p.exists():
        # A MISSING FIXTURE IS A FAILURE, NOT AN EMPTY SUCCESS. The mock path
        # gets the same discipline as the live one or it proves nothing.
        return C.WorkerResult.failure(
            call, 'MOCK_FIXTURE_ABSENT',
            f'no fixture at {p}. MOCK mode does not invent a response any '
            f'more than LIVE mode does.')
    try:
        fixture = json.loads(p.read_text())
    except ValueError as exc:
        return C.WorkerResult.failure(call, 'MOCK_FIXTURE_UNPARSEABLE',
                                      f'{p}: {exc}')
    # A fixture may deliberately describe a FAILURE, so the state machine's
    # failure paths can be exercised without breaking anything real.
    if fixture.get('simulate_failure'):
        esc = fixture.get('escalation')
        return C.WorkerResult.failure(
            call, fixture.get('code', 'MOCK_SIMULATED_FAILURE'),
            fixture.get('detail', 'fixture requested a failure'),
            raw=fixture,
            escalation=C.Escalation(esc) if esc else None)
    parsed = fixture.get('parsed')
    if not isinstance(parsed, dict) or not parsed:
        return C.WorkerResult.failure(
            call, 'MOCK_FIXTURE_EMPTY',
            f'{p} carries no `parsed` object')
    return C.WorkerResult(call=call, ok=True, code='WORKER_OK',
                          detail=f'mock fixture {p.name}',
                          raw=fixture, parsed=parsed,
                          usage=fixture.get('usage')
                          or {'total_tokens': 0, 'mocked': True})


# ---------------------------------------------------------------- call
def call_worker(call, worker, model_cfg, system, user, *, task_id,
                env=None, timeout=None) -> C.WorkerResult:
    """One provider call. Returns a WorkerResult; never raises for API trouble.

    Exceptions are for programming errors. An API that is down, slow, angry or
    incoherent is DATA about the run, and data belongs in a result the caller
    can log -- not in a traceback that loses the request that caused it.
    """
    env = env if env is not None else os.environ
    if mode(env) == MODE_MOCK:
        return _mock(call, worker, task_id)

    provider = model_cfg['provider']
    key = (env.get(SECRET_ENV[provider]) or '').strip()
    if not key:
        # Reached only if a caller skipped locks.require_secret. Still refuses.
        return C.WorkerResult.failure(
            call, 'SECRET_MISSING',
            f'{SECRET_ENV[provider]} is unset; not falling back to a mock.',
            escalation=C.Escalation.SECRET_MISSING)

    body = _request_body(provider, model_cfg, system, user)
    started = time.time()
    try:
        status, raw = _post(ENDPOINTS[provider], _headers(provider, key),
                            body, timeout or 600)
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', 'replace')[:2000]
        except Exception:                                    # noqa: BLE001
            pass
        esc = (C.Escalation.COST_LIMIT_REACHED if exc.code == 429 else None)
        return C.WorkerResult.failure(
            call, f'API_HTTP_{exc.code}',
            f'{provider} returned {exc.code}: {detail}',
            raw={'status': exc.code, 'body': detail}, escalation=esc)
    except urllib.error.URLError as exc:
        return C.WorkerResult.failure(
            call, 'API_UNREACHABLE', f'{provider}: {exc.reason}')
    except TimeoutError:
        return C.WorkerResult.failure(
            call, 'API_TIMEOUT',
            f'{provider} did not answer within {timeout or 600}s. Recorded as '
            f'a failure; a timeout is not a refusal and not a success.')
    except Exception as exc:                                 # noqa: BLE001
        return C.WorkerResult.failure(
            call, 'API_EXCEPTION', f'{type(exc).__name__}: {exc}')

    elapsed = round(time.time() - started, 2)
    if status >= 300:
        return C.WorkerResult.failure(
            call, f'API_HTTP_{status}', f'{provider} returned {status}',
            raw={'status': status})
    if not raw:
        return C.WorkerResult.failure(
            call, 'API_EMPTY_BODY',
            f'{provider} returned {status} with an empty body')
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        return C.WorkerResult.failure(
            call, 'API_UNPARSEABLE', f'{provider}: {exc}',
            raw={'body': raw.decode('utf-8', 'replace')[:4000]})

    text = _extract_text(provider, payload)
    if not text.strip():
        return C.WorkerResult.failure(
            call, 'MODEL_EMPTY_RESPONSE',
            f'{provider} returned a well-formed response containing no text. '
            f'An empty answer is a failed call.', raw=payload)

    parsed, perr = parse_structured(text)
    if parsed is None:
        return C.WorkerResult.failure(
            call, 'MODEL_MALFORMED_RESPONSE',
            f'{provider} returned text that is not the JSON object the '
            f'contract asked for: {perr}', raw=payload)

    usage = _usage(provider, payload)
    usage['elapsed_s'] = elapsed
    return C.WorkerResult(call=call, ok=True, code='WORKER_OK',
                          detail=f'{provider} {status} in {elapsed}s',
                          raw=payload, parsed=parsed, usage=usage)


def parse_structured(text: str):
    """The JSON object a worker was asked for, or (None, why).

    Models fence JSON in ``` blocks and add a sentence before it. That is
    tolerated. What is NOT tolerated is guessing: if no object parses, this
    returns None and the caller records a malformed response. Reconstructing
    what the model "probably meant" is how a bad return becomes a committed
    artifact.
    """
    t = (text or '').strip()
    if '```' in t:
        chunks = t.split('```')
        for i in range(1, len(chunks), 2):
            body = chunks[i]
            if body.lstrip().lower().startswith('json'):
                body = body.lstrip()[4:]
            body = body.strip()
            try:
                obj = json.loads(body)
                if isinstance(obj, dict):
                    return obj, None
            except ValueError:
                continue
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj, None
        return None, f'top level is {type(obj).__name__}, not an object'
    except ValueError:
        pass
    start, end = t.find('{'), t.rfind('}')
    if start >= 0 and end > start:
        try:
            obj = json.loads(t[start:end + 1])
            if isinstance(obj, dict):
                return obj, None
        except ValueError as exc:
            return None, str(exc)
    return None, 'no JSON object found in the response'
