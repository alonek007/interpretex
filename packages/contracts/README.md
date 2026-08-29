# interpretex-contracts — BOOTSTRAP SHIM (dev placeholder)

> **Status:** This package is nominally **owned by Part 1** (`part1-world` branch).
> It does **not** exist yet on `main` (the GitHub repo was empty at build time), so
> Part 2 authored this minimal, spec-exact implementation from the frozen contract
> in `docs/00_MASTER_PLAN.md` §8 to unblock development and testing.
>
> **When Part 1's authoritative `packages/contracts/` lands on `main`:** delete this
> directory, `pip install -e packages/contracts` from the real one, and re-run
> `pytest tests/agent`. Nothing in `packages/agent/` needs to change — it imports
> only names defined in §8, with `extra="forbid"` pydantic v2 models.
>
> Per the freeze rule, any field drift between this shim and Part 1's package is a
> team-level contract change and must be agreed by all three parts.
