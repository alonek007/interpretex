# STEP-05 — Frozen contracts

`packages/contracts/interpretex_contracts/` (see `docs/10_CONTRACTS.md`).

The contract is the only thing Parts 2 and 3 import. It is frozen for the
hackathon at `CONTRACT_VERSION = "1.0.0"` and has **zero** dependency on
`interpretex_world`, so it installs and its fixtures validate standalone.

It defines three seams as `typing.Protocol`:
- `ToolRegistry` — case-scoped `specs()` / `call()` (never raises)
- `LLMClient` — `complete` / `complete_json`
- `WorldAPI` — `list_cases`, `load_case`, `generate_case`, `build_tool_registry`,
  `network_view`, `attack`
- `Investigator` — Part 2's `investigate` / `investigate_stream`

`AgentCaseView` (produced by `TradeCase.to_agent_view()`) strips the label and all
world-side context so the agent cannot read the intended verdict. Every
`InvestigationResult` carries `STANDARD_CAVEATS` and a replayable `events` list with
a gapless `seq`.
