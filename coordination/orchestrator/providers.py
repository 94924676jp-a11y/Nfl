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

#: endpoint name -> provider -> URL. Named rather than positional so
#: MODELS.json can say which surface a model is served on, and so adding the
#: OpenAI Responses API later is a row here plus a response parser -- not a
#: rewrite. See MODELS.json `endpoint_choice_note` for why chat/completions is
#: the right surface for this runtime today.
ENDPOINTS = {
    'chat_completions': {
        'openai': 'https://api.openai.com/v1/chat/completions',
        'perplexity': 'https://api.perplexity.ai/chat/completions',
    },
    'messages': {
        'anthropic': 'https://api.anthropic.com/v1/messages',
    },
}
_DEFAULT_ENDPOINT = {'openai': 'chat_completions',
                     'perplexity': 'chat_completions',
                     'anthropic': 'messages'}
SECRET_ENV = {
    'openai': 'OPENAI_API_KEY',
    'anthropic': 'ANTHROPIC_API_KEY',
    'perplexity': 'PERPLEXITY_API_KEY',
}


#: A test hook. When set to a list, a LIVE call is RECORDED rather than sent,
#: and the fixture is returned so the state machine keeps running. It exists so
#: LIVE semantics can be proven without spending a cent. It is never set by
#: production code -- only a test assigns it, exactly like MOCKS.
SPY = None


def requested_mode(env=None) -> str:
    """What the RUNTIME was asked for. A request, not an authorization."""
    env = env if env is not None else os.environ
    return MODE_LIVE if (env.get('AUTONOMY_MODE') or '').upper() == 'LIVE' \
        else MODE_MOCK


def policy_mode(policy) -> str:
    """What the PROTECTED POLICY authorizes. The ceiling.

    Absent or unrecognised reads as MOCK. A missing field must never be the
    permissive case: the whole point of putting this in a committed file is
    that spending requires someone to have written the word LIVE into it.
    """
    m = str((policy or {}).get('execution_mode') or MODE_MOCK).upper()
    return MODE_LIVE if m == MODE_LIVE else MODE_MOCK


def resolve_mode(policy, env=None) -> str:
    """The effective mode. LIVE needs the POLICY and the request to agree.

    THE AUTHORITY MODEL, IN ONE FUNCTION.

      policy is the CEILING  -- it can only be set by editing a protected file
                                on the automation branch, which no worker may
                                touch, and it is what makes LIVE survive a
                                continuation without a human clicking again;
      the env var is a REQUEST -- it can only RESTRICT, never escalate.

    So LIVE happens only when `autonomous_operation_enabled` is true AND
    `execution_mode` is LIVE AND the runtime was asked for LIVE. Any of the
    three saying otherwise gives MOCK, and no event payload appears anywhere
    in that sentence.

    An earlier dispatcher resolved this from the payload and then, correctly,
    refused to trust it -- which made LIVE unable to survive its own first
    continuation. The refusal was right; the location was wrong.
    """
    if not (policy or {}).get('autonomous_operation_enabled'):
        return MODE_MOCK
    if policy_mode(policy) != MODE_LIVE:
        return MODE_MOCK
    return requested_mode(env)


def mode(env=None) -> str:
    """Deprecated shorthand: the REQUEST only, with no policy consulted.

    Kept because `write_run` records what the runtime was asked for, which is
    a different fact from what it was allowed to do. Never use it to decide
    whether to spend money -- that is `resolve_mode`.
    """
    return requested_mode(env)


# ------------------------------------------------------------ the wire
def _post(url, headers, body, timeout) -> tuple:
    """(status, bytes) or raises. No retry here -- policy owns retries."""
    req = urllib.request.Request(
        url, data=json.dumps(body).encode('utf-8'), method='POST',
        headers={'Content-Type': 'application/json', **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def _request_body(provider, model_cfg, system, user):
    """Each provider's shape. Which PARAMETERS to send is data, not a branch.

    THE FIRST VERSION OF THIS FUNCTION WOULD HAVE 400ed ON EVERY LIVE CALL.
    It hard-coded `temperature: 0` for all three providers and `max_tokens`
    for the two chat-completions ones. Both current flagship reasoning models
    REJECT sampling parameters rather than ignoring them:

      claude-opus-5   temperature/top_p/top_k removed -> HTTP 400
      gpt-5.6-sol     temperature -> HTTP 400 "Only the default (1) value is
                      supported", and it takes max_completion_tokens, not
                      max_tokens

    Nothing in the mocked suite could have caught that, because a mock answers
    whatever the fixture says. It took reading the providers' current
    documentation, which is the one thing a sandbox cannot do for itself.

    So the parameter set now comes from MODELS.json `params`, and `omit` is
    carried as an explicit refusal list rather than as silence -- a reader can
    see that temperature was left out ON PURPOSE rather than forgotten. A
    provider that changes its surface is then a diff in a config file on a
    protected path, not a rewrite of the transport.
    """
    body = {'model': model_cfg['model']}
    params = dict(model_cfg.get('params') or {})
    omit = set(model_cfg.get('omit') or ())
    for k in omit:
        params.pop(k, None)     # belt and braces: omit wins over params
    body.update(params)

    if provider == 'anthropic':
        body['system'] = system
        body['messages'] = [{'role': 'user', 'content': user}]
        # Thinking is deliberately NOT set. On claude-opus-5 omitting it runs
        # adaptive thinking, which is what this worker wants; passing
        # {type: "disabled"} or a budget_tokens would be a 400.
        return body
    # openai and perplexity are both chat/completions shaped.
    body['messages'] = [{'role': 'system', 'content': system},
                        {'role': 'user', 'content': user}]
    return body


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
                env=None, timeout=None, effective_mode=None) -> C.WorkerResult:
    """One provider call. Returns a WorkerResult; never raises for API trouble.

    Exceptions are for programming errors. An API that is down, slow, angry or
    incoherent is DATA about the run, and data belongs in a result the caller
    can log -- not in a traceback that loses the request that caused it.
    """
    env = env if env is not None else os.environ

    # THE SECOND LOCK, AND THE ONE THAT MATTERS MOST.
    #
    # The dispatcher already derives the mode from the protected policy. This
    # check exists so that is not the ONLY thing standing between a malformed
    # event and a bill. A caller that skipped the dispatcher, or passed the
    # wrong thing, still cannot reach a provider: `effective_mode` must be
    # LIVE and it must have been computed by `resolve_mode` from the policy.
    # Absent, it defaults to the request alone -- which is why every caller in
    # this runtime passes it explicitly and `main._call` reads the policy.
    if effective_mode is None:
        effective_mode = requested_mode(env)
    if effective_mode != MODE_LIVE:
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
    if SPY is not None:
        # A LIVE call that is recorded instead of sent. The state machine gets
        # a fixture back so the chain continues, and the test can assert
        # exactly which provider WOULD have been paid, on which pass.
        SPY.append({'worker': worker.value, 'provider': provider,
                    'model': model_cfg['model'], 'task_id': task_id,
                    'endpoint': model_cfg.get('endpoint'),
                    'body_keys': sorted(k for k in body if k != 'messages'),
                    'mode': 'LIVE'})
        out = _mock(call, worker, task_id)
        out.detail = f'LIVE call to {provider} RECORDED BY SPY, not sent'
        return out
    endpoint = ENDPOINTS.get(model_cfg.get('endpoint')
                             or _DEFAULT_ENDPOINT[provider], {}).get(provider)
    if endpoint is None:
        return C.WorkerResult.failure(
            call, 'ENDPOINT_UNKNOWN',
            f'MODELS.json asks for endpoint '
            f'{model_cfg.get("endpoint")!r} on {provider}, which this '
            f'transport does not implement. Refusing rather than guessing.')
    started = time.time()
    try:
        status, raw = _post(endpoint, _headers(provider, key),
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
