# mock_returns

**Engineering returns, not provider responses.** These are a different contract
from `../mocks/`, and mixing the two is what put a fixture named for the Claude
Code Action into a directory a guard watches.

| directory | artifact | shape | consumer |
|---|---|---|---|
| `../mocks/` | what a model provider would have returned | `{parsed, usage}` | `providers._mock` |
| `mock_returns/` | what a WORKER returns for an engineering task | `{commands_run, tests, refusals, governance_checks, result_status}` | `mock_worker` |

Naming: `engineer.<task_id>.json` if present, else `engineer.default.json`.

**A fixture here may never claim to be a response from the Claude Code
Action.** `test_orchestrator` enforces both halves — no fixture named for the
Action, and no fixture whose content asserts it is one. The MOCK worker is its
own worker, stamped `executed_by: MOCK_WORKER`; it does not impersonate the
paid path. A fixture that did would let a test pass while the Action was never
exercised, and no artifact would record the difference.

**A missing fixture is a refusal, never an empty success** —
`MOCK_FIXTURE_ABSENT`. A mock worker with no fixture would be inventing a
result.
