# STEP-07 — Demo cases

`packages/world/interpretex_world/demo.py` (pinned to the brief's exact figures).

The three demo cases are built by `build_case_from_blueprint`: every value is
explicit because `CaseSpec` cannot carry ports/vessel/dates by contract, so the
cases are stable by construction and byte-reproducible from their seeds.

- **`case_clean_001`** — coffee, RELEASE expected. Every dimension clean; no
  observation above `low`.
- **`case_explainable_002`** — aluminium −18% under benchmark, but a genuine
  three-year offtake contract (in the file) and the importer's own history at
  $1,940–$2,010/t. HOLD expected; exactly **one** `medium` (the economic price
  gap, explained by the contract). Never ESCALATE.
- **`case_suspicious_003`** — copper: under-invoicing −38.2%, capacity 122%,
  one-day transit, insurance 8 days after shipment, packing list describes Copper
  Scrap, recurring broker. ESCALATE expected on **4+ dimensions** (lands 7 high).
- **`case_adv_004`** — the attacker's fallback (see STEP-04). Every signal low or
  medium; only their correlation is informative.

Seeds: `SEED_1=1001`, `SEED_2=2002`, `SEED_3=3003`, `SEED_ADV=4004`.
