"""Document renderer: one shipment -> the case file.

Each document is a TradeDocument whose ``fields`` use canonical TradeRecord
names wherever the concept exists there (so cross-document comparison is a
dict intersection) and whose ``raw_text`` is a plausible document layout that
contains exactly the same values as ``fields`` — Part 3 renders raw_text in a
document viewer and the values must match.

Field-level realism: different documents legitimately carry different subsets.
A bill of lading has no unit price; a packing list has gross/net weight and
package counts; a certificate of origin has the HS code and a chamber-of-
commerce reference.
"""

from __future__ import annotations

from datetime import date, timedelta

from interpretex_contracts import DocType, TradeDocument

from .reference import load_world
from .shipment import Shipment

#: canonical "what was shipped" description per doc role is carried on the
#: Shipment itself; issuer names are fixed fictional institutions of the
#: synthetic world.
IMPORTER_BANK = "Harbour Commercial Bank"
EXPORTER_BANK = "Gateway Trade Bank"
CHAMBER = "Singapore Chamber of Commerce & Industry"

CONFIDENCE = {
    DocType.letter_of_credit: 0.98,
    DocType.commercial_invoice: 0.97,
    DocType.bill_of_lading: 0.95,
    DocType.packing_list: 0.94,
    DocType.certificate_of_origin: 0.96,
    DocType.insurance_certificate: 0.97,
    DocType.inspection_certificate: 0.93,
    DocType.sales_contract: 0.99,
}


def _fmt_money(v: float, currency: str) -> str:
    return f"{currency} {v:,.2f}"


def _fmt_qty(v: float) -> str:
    return f"{v:,.2f}"


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def _doc(shipment: Shipment, doc_type: DocType, doc_id: str, issuer: str,
         issue_date: str, fields: dict, raw_text: str) -> TradeDocument:
    return TradeDocument(
        doc_id=doc_id,
        doc_type=doc_type,
        issuer=issuer,
        issue_date=issue_date,
        fields=fields,
        raw_text=raw_text.strip("\n"),
        extraction_confidence=CONFIDENCE[doc_type],
    )


# --------------------------------------------------------------- per-type ----


def _letter_of_credit(s: Shipment) -> TradeDocument:
    exporter = load_world().entity(s.exporter_id)["name"]
    importer = load_world().entity(s.importer_id)["name"]
    expiry = (_d(s.lc_issue_date) + timedelta(days=90)).isoformat()
    fields = {
        "lc_number": s.lc_number,
        "issue_date": s.lc_issue_date,
        "applicant_name": importer,
        "applicant_id": s.importer_id,
        "beneficiary_name": exporter,
        "beneficiary_id": s.exporter_id,
        "commodity": s.description,
        "commodity_grade": s.commodity_grade,
        "quantity": s.quantity,
        "unit": s.unit,
        "unit_price": s.unit_price,
        "currency": s.currency,
        "total_value": s.total_value,
        "incoterm": s.incoterm,
        "latest_shipment_date": s.ship_date,
        "origin_port": s.origin_port,
        "destination_port": s.destination_port,
        "expiry_date": expiry,
        "required_documents": "commercial_invoice; bill_of_lading; packing_list; "
                              "certificate_of_origin; insurance_certificate",
    }
    raw = f"""
        IRREVOCABLE DOCUMENTARY LETTER OF CREDIT
        ========================================
        Issuing Bank:        {IMPORTER_BANK}
        LC Number:           {fields['lc_number']}
        Date of Issue:       {fields['issue_date']}
        Date of Expiry:      {fields['expiry_date']}

        Applicant:           {fields['applicant_name']} ({fields['applicant_id']})
        Beneficiary:         {fields['beneficiary_name']} ({fields['beneficiary_id']})

        Goods:               {fields['commodity']}
        Grade/Spec:          {fields['commodity_grade']}
        Quantity:            {_fmt_qty(fields['quantity'])} {fields['unit']}
        Unit Price:          {_fmt_money(fields['unit_price'], fields['currency'])} per {fields['unit']}
        Total Amount:        {_fmt_money(fields['total_value'], fields['currency'])}
        Terms of Delivery:   {fields['incoterm']}
        Port of Loading:     {fields['origin_port']}
        Port of Discharge:   {fields['destination_port']}
        Latest Shipment:     {fields['latest_shipment_date']}

        Required Documents:  {fields['required_documents']}

        We hereby engage with the drawers, endorsers and bona fide holders that
        drafts drawn under and in compliance with the terms of this credit will
        be duly honoured on presentation.

        Authorised Signature: J. Whitfield, Trade Finance Operations
    """
    return _doc(s, DocType.letter_of_credit, s.doc_ids["letter_of_credit"],
                IMPORTER_BANK, s.lc_issue_date, fields, raw)


def _commercial_invoice(s: Shipment) -> TradeDocument:
    exporter = load_world().entity(s.exporter_id)["name"]
    importer = load_world().entity(s.importer_id)["name"]
    fields = {
        "commodity": s.description,
        "commodity_grade": s.commodity_grade,
        "hs_code": s.hs_code,
        "quantity": s.quantity,
        "unit": s.unit,
        "unit_price": s.unit_price,
        "currency": s.currency,
        "total_value": s.total_value,
        "incoterm": s.incoterm,
        "exporter_id": s.exporter_id,
        "exporter_name": exporter,
        "importer_id": s.importer_id,
        "importer_name": importer,
        "contract_reference": s.contract_reference,
        "country_of_origin": s.country_of_origin,
        "lc_number": s.lc_number,
        "line_items": [{
            "description": f"{s.description}, {s.commodity_grade}",
            "quantity": s.quantity,
            "unit_price": s.unit_price,
            "amount": s.total_value,
        }],
    }
    item = fields["line_items"][0]
    raw = f"""
        COMMERCIAL INVOICE
        ==================
        Invoice No:          {s.doc_ids['commercial_invoice']}
        Date:                {_d(s.ship_date) - timedelta(days=1):%Y-%m-%d}
        LC Reference:        {fields['lc_number']}
        Contract Reference:  {fields['contract_reference'] or 'n/a'}

        Seller/Exporter:     {fields['exporter_name']} ({fields['exporter_id']})
        Buyer/Importer:      {fields['importer_name']} ({fields['importer_id']})

        Line Items
        ----------
        1. Description:      {item['description']}
           Quantity:         {_fmt_qty(item['quantity'])} {fields['unit']}
           Unit Price:       {_fmt_money(item['unit_price'], fields['currency'])} per {fields['unit']}
           Amount:           {_fmt_money(item['amount'], fields['currency'])}

        HS Code:             {fields['hs_code']}
        Country of Origin:   {fields['country_of_origin']}
        Terms of Delivery:   {fields['incoterm']}

        TOTAL INVOICE VALUE: {_fmt_money(fields['total_value'], fields['currency'])}

        E. & O.E. — Authorised Signature: M. Delacroix, Export Sales
    """
    return _doc(s, DocType.commercial_invoice, s.doc_ids["commercial_invoice"],
                exporter, (_d(s.ship_date) - timedelta(days=1)).isoformat(), fields, raw)


def _bill_of_lading(s: Shipment) -> TradeDocument:
    exporter = load_world().entity(s.exporter_id)["name"]
    importer = load_world().entity(s.importer_id)["name"]
    fields = {
        "bl_number": s.bl_number,
        "vessel_name": s.vessel_name,
        "imo": s.imo,
        "origin_port": s.origin_port,
        "destination_port": s.bl_destination_port,
        "ship_date": s.ship_date,
        "arrival_date": s.arrival_date,
        "container_count": s.container_count,
        "gross_weight_tons": s.gross_weight_tons,
        "commodity": s.description,
        "exporter_id": s.exporter_id,
        "exporter_name": exporter,
        "importer_id": s.importer_id,
        "importer_name": importer,
        "lc_number": s.lc_number,
    }
    raw = f"""
        BILL OF LADING (SHIPPED ON BOARD)
        =================================
        B/L Number:          {fields['bl_number']}
        Date of Issue:       {fields['ship_date']}
        Shipper:             {fields['exporter_name']} ({fields['exporter_id']})
        Consignee:           {fields['importer_name']} ({fields['importer_id']})

        Vessel / Voyage:     {fields['vessel_name']} (IMO {fields['imo']})
        Port of Loading:     {fields['origin_port']}
        Port of Discharge:   {fields['destination_port']}
        Shipped on Board:    {fields['ship_date']}

        Description of Goods: {fields['commodity']}
        Containers:          {fields['container_count']}
        Gross Weight:        {_fmt_qty(fields['gross_weight_tons'])} MT

        Freight payable as per charter party. Goods received in apparent good
        order and condition.

        Master's Signature:  Capt. H. Okonkwo
    """
    return _doc(s, DocType.bill_of_lading, s.doc_ids["bill_of_lading"],
                s.vessel_name.split()[0] + " Line", s.ship_date, fields, raw)


def _packing_list(s: Shipment) -> TradeDocument:
    exporter = load_world().entity(s.exporter_id)["name"]
    fields = {
        "commodity": s.packing_description,
        "quantity": s.packing_quantity,
        "unit": s.unit,
        "net_weight_tons": s.net_weight_tons,
        "gross_weight_tons": s.gross_weight_tons,
        "package_count": s.package_count,
        "container_count": s.container_count,
        "origin_port": s.origin_port,
        "destination_port": s.bl_destination_port,
        "ship_date": s.ship_date,
        "exporter_name": exporter,
    }
    raw = f"""
        PACKING LIST
        ============
        Packing List No:     {s.doc_ids['packing_list']}
        Date:                {fields['ship_date']}
        Exporter:            {fields['exporter_name']}

        Goods Description:   {fields['commodity']}
        Quantity:            {_fmt_qty(fields['quantity'])} {fields['unit']}
        Packages:            {fields['package_count']}
        Containers:          {fields['container_count']}
        Net Weight:          {_fmt_qty(fields['net_weight_tons'])} MT
        Gross Weight:        {_fmt_qty(fields['gross_weight_tons'])} MT

        Port of Loading:     {fields['origin_port']}
        Port of Discharge:   {fields['destination_port']}

        All packages marked: KEEP DRY — THIS SIDE UP
        Packed and checked by: Warehouse Operations, {fields['exporter_name']}
    """
    return _doc(s, DocType.packing_list, s.doc_ids["packing_list"],
                exporter, s.ship_date, fields, raw)


def _certificate_of_origin(s: Shipment) -> TradeDocument:
    exporter = load_world().entity(s.exporter_id)["name"]
    importer = load_world().entity(s.importer_id)["name"]
    fields = {
        "commodity": s.description,
        "hs_code": s.coo_hs_code,
        "quantity": s.quantity,
        "unit": s.unit,
        "origin_country": s.country_of_origin,
        "country_of_origin": s.country_of_origin,
        "exporter_id": s.exporter_id,
        "exporter_name": exporter,
        "importer_name": importer,
        "chamber_reference": f"COO/{s.country_of_origin}/{s.doc_ids['certificate_of_origin'].split('-', 1)[-1]}",
        "ship_date": s.ship_date,
    }
    raw = f"""
        CERTIFICATE OF ORIGIN
        =====================
        Certificate No:      {s.doc_ids['certificate_of_origin']}
        Date:                {(_d(s.ship_date) - timedelta(days=2)):%Y-%m-%d}
        Chamber Reference:   {fields['chamber_reference']}

        Exporter:            {fields['exporter_name']} ({fields['exporter_id']})
        Consignee:           {fields['importer_name']}

        Goods:               {fields['commodity']}
        HS Code:             {fields['hs_code']}
        Quantity:            {_fmt_qty(fields['quantity'])} {fields['unit']}
        Country of Origin:   {fields['country_of_origin']}

        The undersigned certifies that the goods described above originate in
        {fields['country_of_origin']}.

        Chamber of Commerce: {CHAMBER}
        Authorised Signatory: R. Vasquez
    """
    return _doc(s, DocType.certificate_of_origin, s.doc_ids["certificate_of_origin"],
                CHAMBER, (_d(s.ship_date) - timedelta(days=2)).isoformat(), fields, raw)


def _insurance_certificate(s: Shipment) -> TradeDocument:
    insurer = load_world().entity(s.insurer_id)["name"] if s.insurer_id else "Oceanus Marine Insurance Ltd"
    exporter = load_world().entity(s.exporter_id)["name"]
    importer = load_world().entity(s.importer_id)["name"]
    insured_value = round(s.total_value * 1.1, 2)
    fields = {
        "insurance_issue_date": s.insurance_issue_date,
        "commodity": s.description,
        "insured_value": insured_value,
        "currency": s.currency,
        "vessel_name": s.vessel_name,
        "origin_port": s.origin_port,
        "destination_port": s.bl_destination_port,
        "ship_date": s.ship_date,
        "exporter_name": exporter,
        "importer_name": importer,
        "policy_number": s.doc_ids["insurance_certificate"],
        "insurer_id": s.insurer_id or "ENT-009",
        "lc_number": s.lc_number,
    }
    raw = f"""
        MARINE CARGO INSURANCE CERTIFICATE
        ==================================
        Policy/Certificate:  {fields['policy_number']}
        Date of Issue:       {fields['insurance_issue_date']}
        Insurer:             {insurer}

        The Insured:         {fields['exporter_name']} / {fields['importer_name']}
        Subject Matter:      {fields['commodity']}
        Voyage:              {fields['origin_port']} to {fields['destination_port']}
        Conveyance:          {fields['vessel_name']}
        Shipment Date:       {fields['ship_date']}

        Insured Value:       {_fmt_money(fields['insured_value'], fields['currency'])}
        Conditions:          Institute Cargo Clauses (A), Institute War Clauses,
                             Institute Strikes Clauses

        Claims payable at destination in currency of this certificate.
        Authorised Signatory: P. Lindqvist, Marine Underwriting
    """
    return _doc(s, DocType.insurance_certificate, s.doc_ids["insurance_certificate"],
                insurer, s.insurance_issue_date, fields, raw)


def _sales_contract(s: Shipment) -> TradeDocument:
    exporter = load_world().entity(s.exporter_id)["name"]
    importer = load_world().entity(s.importer_id)["name"]
    world = load_world()
    commodity = world.commodity(s.commodity_key)
    clause_texts = {
        "long_term_offtake": (
            f"This Agreement ({s.contract_reference}) establishes a three (3) year "
            "offtake relationship commencing 1 January 2025, under which the Buyer "
            "shall purchase a minimum of "
            f"{_fmt_qty(s.quantity)} {s.unit} per calendar year of the goods described herein."),
        "bulk_discount": (
            "Pricing follows the volume-tier schedule in Annex A: 4.0% below the "
            "published reference price for annual volumes of 1,000 to 2,499 "
            f"{s.unit}, and 7.0% below the published reference price for annual "
            f"volumes of 2,500 {s.unit} and above."),
        "grade_difference": (
            f"The goods supplied under this Agreement conform to {s.commodity_grade}, "
            "a commercial grade priced by agreement of the parties rather than by "
            "reference to the standard exchange quotation."),
        "distressed_sale": (
            "The Seller warrants this is a one-time clearance of surplus warehouse "
            "stock offered at a negotiated discount, and not part of ordinary "
            "commercial supply."),
        "inspection": (
            "An independent pre-shipment inspection of quantity and quality shall be "
            "conducted at the port of loading, and the inspection certificate shall "
            "form part of the documentary presentation."),
    }
    clauses = {claim: clause_texts[claim] for claim in s.contract_claims
               if claim in clause_texts}
    fields = {
        "contract_reference": s.contract_reference,
        "commodity": s.description,
        "commodity_grade": s.commodity_grade,
        "quantity": s.quantity,
        "unit": s.unit,
        "unit_price": s.unit_price,
        "currency": s.currency,
        "exporter_name": exporter,
        "importer_name": importer,
        "exporter_id": s.exporter_id,
        "importer_id": s.importer_id,
        "term": "three (3) years" if "long_term_offtake" in clauses else "one (1) shipment",
        "clauses": clauses,
        "issue_date": (_d(s.lc_issue_date) - timedelta(days=30)).isoformat(),
    }
    clause_lines = "\n".join(
        f"  Clause {chr(65 + i)} — {claim.replace('_', ' ').title()}:\n"
        f"    \"{text}\""
        for i, (claim, text) in enumerate(clauses.items()))
    raw = f"""
        SALES AND PURCHASE AGREEMENT
        ============================
        Agreement Reference: {fields['contract_reference']}
        Date:                {fields['issue_date']}
        Term:                {fields['term']}

        Seller:              {fields['exporter_name']} ({fields['exporter_id']})
        Buyer:               {fields['importer_name']} ({fields['importer_id']})

        Goods:               {fields['commodity']} ({fields['commodity_grade']})
        Annual Quantity:     {_fmt_qty(fields['quantity'])} {fields['unit']}
        Price Basis:         {_fmt_money(fields['unit_price'], fields['currency'])} per {fields['unit']}

        Selected Clauses:
{clause_lines}

        Signed for and on behalf of the parties:
        {fields['exporter_name']} — L. Ferreira    {fields['importer_name']} — A. de Vries
    """
    return _doc(s, DocType.sales_contract, s.doc_ids["sales_contract"],
                f"{exporter} / {importer}", fields["issue_date"], fields, raw)


def _inspection_certificate(s: Shipment) -> TradeDocument:
    exporter = load_world().entity(s.exporter_id)["name"]
    fields = {
        "commodity": s.description,
        "commodity_grade": s.commodity_grade,
        "quantity": s.quantity,
        "unit": s.unit,
        "inspection_result": "in conformance",
        "inspection_date": (_d(s.ship_date) - timedelta(days=1)).isoformat(),
        "exporter_name": exporter,
        "vessel_name": s.vessel_name,
    }
    raw = f"""
        PRE-SHIPMENT INSPECTION CERTIFICATE
        ===================================
        Certificate No:      {s.doc_ids['inspection_certificate']}
        Date of Inspection:  {fields['inspection_date']}
        Inspector:           Meridian Inspection Services (independent)

        Goods Inspected:     {fields['commodity']} ({fields['commodity_grade']})
        Quantity Verified:   {_fmt_qty(fields['quantity'])} {fields['unit']}
        Conveyance:          {fields['vessel_name']}
        Result:              {fields['inspection_result'].title()}

        Quantity and quality were found to conform to the contractual
        specification. Samples retained for 90 days.
        Authorised Signatory: T. Nakamura
    """
    return _doc(s, DocType.inspection_certificate, s.doc_ids["inspection_certificate"],
                "Meridian Inspection Services", fields["inspection_date"], fields, raw)


_RENDERERS = {
    DocType.letter_of_credit: _letter_of_credit,
    DocType.commercial_invoice: _commercial_invoice,
    DocType.bill_of_lading: _bill_of_lading,
    DocType.packing_list: _packing_list,
    DocType.certificate_of_origin: _certificate_of_origin,
    DocType.insurance_certificate: _insurance_certificate,
    DocType.sales_contract: _sales_contract,
    DocType.inspection_certificate: _inspection_certificate,
}

#: stable document order of the case file
DOCUMENT_ORDER = [
    DocType.letter_of_credit,
    DocType.sales_contract,
    DocType.commercial_invoice,
    DocType.bill_of_lading,
    DocType.packing_list,
    DocType.certificate_of_origin,
    DocType.insurance_certificate,
    DocType.inspection_certificate,
]


def render_documents(s: Shipment) -> list[TradeDocument]:
    """Render the whole case file from one shipment. The sales contract is
    included iff the shipment carries contract claims; the inspection
    certificate iff ``inspect_before_shipment`` is set."""
    out: list[TradeDocument] = []
    for doc_type in DOCUMENT_ORDER:
        if doc_type is DocType.sales_contract and not s.contract_claims:
            continue
        if doc_type is DocType.inspection_certificate and not s.inspect_before_shipment:
            continue
        out.append(_RENDERERS[doc_type](s))
    return out
