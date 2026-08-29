# STEP-02 — Document layer

`packages/world/interpretex_world/documents.py`, `shipment.py`, `extraction.py`.

A `Shipment` is the **single source of truth**. The eight documents — commercial
invoice, letter of credit, bill of lading, packing list, certificate of origin,
insurance certificate, and (optionally) sales contract + inspection certificate —
are *rendered* from it. Anomaly injectors mutate the `Shipment`; documents are
re-rendered afterwards, so every anomaly shows up wherever it should.

`extract(documents)` builds the canonical `TradeRecord` with explicit precedence:
LC/invoice win on commercial terms, BL wins on transport, packing list wins on
weights. Disagreements are **never** silently reconciled — the winning value is
held in the record and the conflict stays discoverable by
`check_document_consistency`.

Each document carries a flat `fields` dict (for the consistency tool) plus a raw
`text`. The BL includes `arrival_date` so transit plausibility can be checked; the
sales contract renders its `contract_claims` as prose so the
`check_contract_or_supporting_evidence` tool can confirm a stated claim.
