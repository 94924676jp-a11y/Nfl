# mocks

Fixtures for `AUTONOMY_MODE` other than `LIVE`. Each one is what a provider
*would* have returned, in the same shape the live path parses.

**A missing fixture is a failure, not an empty success.** `providers._mock`
returns `MOCK_FIXTURE_ABSENT` rather than a blank response, because the mock
path is only worth having if it is held to the same standard as the live one.

**A missing API key never falls back to a fixture.** `MOCK` has to be asked
for by name. A mock standing in for a call the operator believed they were
making would be a fabricated result wearing a real one's clothes, and it would
be indistinguishable from the real thing in every artifact it produced.

Naming: `<worker>.<task_id>.json` if present, else `<worker>.default.json`.
Workers are `anthropic`, `openai`, `perplexity` (lower-cased `Worker` values).

A fixture may deliberately describe a failure:

```json
{"simulate_failure": true, "code": "API_TIMEOUT", "detail": "...",
 "escalation": "REPEATED_AGENT_FAILURE"}
```

That is how the failure paths get exercised without breaking anything real.
