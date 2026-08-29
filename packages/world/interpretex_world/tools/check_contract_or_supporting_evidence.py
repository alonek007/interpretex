"""check_contract_or_supporting_evidence — is a claimed fact backed by paperwork?"""

from __future__ import annotations

from interpretex_contracts import Dimension, DocType, Observation, Severity, ToolSpec

from .base import ToolOutcome, clip, derived_source, doc_source

SPEC = ToolSpec(
    name="check_contract_or_supporting_evidence",
    description=(
        "Tests whether a stated claim about the trade is actually supported by a "
        "sales contract or, failing that, by an inspection certificate in the case "
        "file. This is the 'supporting evidence' check: a trade claim with no "
        "backing contract is a gap, while a claim that directly contradicts the "
        "contract is a discrepancy. When no contract exists at all, the gap is "
        "reported as a low-severity absence (not an accusation)."
    ),
    dimensions=[Dimension.documentary],
    args_schema={
        "type": "object",
        "properties": {
            "claim": {"type": "string",
                      "description": "the trade fact to verify, e.g. 'grade A copper' or 'USD 8,500/ton'"},
            "doc_type": {"type": "string", "enum": [d.value for d in DocType]},
        },
        "required": ["claim"],
        "additionalProperties": True,
    },
    cost_units=1,
    discriminates=["supported by contract", "contradicts the contract",
                   "no supporting contract on file"],
)


def _text_of(doc) -> str:
    import json
    flat = []
    for k, v in doc.fields.items():
        flat.append(f"{k}: {v if not isinstance(v, (dict, list)) else json.dumps(v)}")
    return "\n".join(flat).lower()


def run(reg, args: dict) -> ToolOutcome:
    claim = (args.get("claim") or "").strip()
    if not claim:
        return ToolOutcome(ok=False, error="argument 'claim' is required")

    claim_l = claim.lower()
    sources = [derived_source("check_contract_or_supporting_evidence", "claim_present", None)]
    observations: list[Observation] = []
    raw: dict = {"claim": claim}

    contract = reg.doc_by_type(DocType.sales_contract)
    inspection = reg.doc_by_type(DocType.inspection_certificate)
    contract_found = contract is not None
    raw["sales_contract_present"] = contract_found
    raw["inspection_certificate_present"] = inspection is not None

    supported_by = []
    contradicted_by = []
    if contract_found:
        ctext = _text_of(contract)
        sources.append(doc_source(contract.doc_id, "fields", contract.doc_id))
        if claim_l in ctext:
            supported_by.append(contract.doc_id)
        else:
            contradicted_by.append(contract.doc_id)
    if inspection is not None:
        itext = _text_of(inspection)
        sources.append(doc_source(inspection.doc_id, "fields", inspection.doc_id))
        if claim_l in itext:
            if not supported_by:
                supported_by.append(inspection.doc_id)
        else:
            if not contradicted_by:
                contradicted_by.append(inspection.doc_id)

    if supported_by:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.documentary,
            statement=(f"The claim '{claim}' is supported by {'/'.join(supported_by)} in the "
                       f"case file."),
            severity=Severity.none,
            metrics={"supporting_docs": float(len(supported_by))},
            sources=sources,
        ))
        summary = clip(f"Claim '{claim}' supported by {'/'.join(supported_by)}.")
    elif contradicted_by and contract_found:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.documentary,
            statement=(f"The claim '{claim}' is NOT supported by the sales contract "
                       f"{contract.doc_id} (nor by the inspection certificate) present in the "
                       f"case file."),
            severity=Severity.medium,
            metrics={"contradicting_docs": float(len(contradicted_by))},
            sources=sources,
        ))
        summary = clip(f"Claim '{claim}' contradicts contract {contract.doc_id}.")
    else:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.documentary,
            statement=(f"No sales contract is present in the case file, so the claim '{claim}' "
                       f"cannot be verified against a contract (supporting-evidence gap)."),
            severity=Severity.low,
            metrics={"sales_contract_present": 0.0},
            sources=sources,
        ))
        summary = clip(f"No sales contract on file; claim '{claim}' unverifiable.")

    raw["supported_by"] = supported_by
    raw["contradicted_by"] = contradicted_by
    return ToolOutcome(ok=True, summary=summary, observations=observations,
                       raw=raw, sources=sources)
