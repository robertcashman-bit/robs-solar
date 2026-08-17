"""Parse bank CSV / OFX / QFX / QIF into normalised import rows."""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%Y%m%d",
)

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "posted_on": (
        "date",
        "transaction date",
        "txn date",
        "posted",
        "posted date",
        "value date",
        "booking date",
        "completed date",
        "transactiondate",
        "dtposted",
    ),
    "description": (
        "description",
        "narrative",
        "details",
        "memo",
        "reference",
        "transaction description",
        "payee",
        "merchant",
        "name",
        "particulars",
        "transaction details",
    ),
    "amount": ("amount", "value", "transaction amount", "gbp", "amt"),
    "debit": (
        "debit",
        "debits",
        "money out",
        "out",
        "withdrawal",
        "paid out",
        "spend",
    ),
    "credit": (
        "credit",
        "credits",
        "money in",
        "in",
        "deposit",
        "paid in",
        "received",
    ),
    "balance": ("balance", "running balance", "account balance", "bal"),
}


def _norm_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("_", " "))


def guess_column_mapping(headers: list[str]) -> dict[str, str]:
    normalised = {_norm_header(header): header for header in headers if header}
    mapping: dict[str, str] = {}
    for field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalised:
                mapping[field] = normalised[alias]
                break
    return mapping


def _parse_date(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    if re.match(r"^\d{8}", text):
        try:
            return datetime.strptime(text[:8], "%Y%m%d").date().isoformat()
        except ValueError:
            pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_amount(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text in {"-", "—", "–"}:
        return None
    text = text.replace("£", "").replace(",", "").replace(" ", "")
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _row_from_mapped(
    *,
    posted_on: str,
    description: str,
    amount: Decimal,
    account_name: str,
    scope: str,
    balance: Decimal | None = None,
    external_id: str = "",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "posted_on": posted_on,
        "description": description[:256],
        "amount_gbp": float(amount),
        "account_name": account_name[:128],
        "scope": scope if scope in {"personal", "business"} else "personal",
    }
    if external_id:
        row["external_id"] = external_id[:128]
    if balance is not None:
        row["balance_gbp"] = float(balance)
    return row


def parse_csv_text(
    text: str,
    *,
    account_name: str,
    scope: str = "personal",
    column_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = list(reader.fieldnames or [])
    mapping = column_mapping or guess_column_mapping(headers)
    rows: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    for index, item in enumerate(reader):
        date_col = mapping.get("posted_on")
        desc_col = mapping.get("description")
        posted = _parse_date(str(item.get(date_col) or "")) if date_col else None
        if not posted:
            rejects.append({"index": index, "reason": "Could not parse date", "row": dict(item)})
            continue
        description = str(item.get(desc_col) or "").strip() if desc_col else ""
        amount: Decimal | None = None
        if mapping.get("amount"):
            amount = _parse_amount(item.get(mapping["amount"]))
        if amount is None and (mapping.get("debit") or mapping.get("credit")):
            debit = _parse_amount(item.get(mapping["debit"])) if mapping.get("debit") else None
            credit = _parse_amount(item.get(mapping["credit"])) if mapping.get("credit") else None
            if credit is not None and credit != 0:
                amount = abs(credit)
            elif debit is not None and debit != 0:
                amount = -abs(debit)
        if amount is None or amount == 0:
            rejects.append({"index": index, "reason": "Could not parse amount", "row": dict(item)})
            continue
        balance = _parse_amount(item.get(mapping["balance"])) if mapping.get("balance") else None
        rows.append(
            _row_from_mapped(
                posted_on=posted,
                description=description or "Imported transaction",
                amount=amount,
                account_name=account_name,
                scope=scope,
                balance=balance,
            )
        )
    return {
        "format": "csv",
        "headers": headers,
        "column_mapping": mapping,
        "rows": rows,
        "rejects": rejects,
        "detected": len(rows) + len(rejects),
    }


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_ofx_text(
    text: str,
    *,
    account_name: str,
    scope: str = "personal",
) -> dict[str, Any]:
    body = text
    match = re.search(r"(<(OFX|ofx)\b)", text)
    if match:
        body = text[match.start() :]
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        try:
            root = ET.fromstring(f"<ROOT>{body}</ROOT>")
        except ET.ParseError as exc:
            return {
                "format": "ofx",
                "headers": [],
                "column_mapping": {},
                "rows": [],
                "rejects": [{"index": 0, "reason": f"Invalid OFX/QFX: {exc}", "row": {}}],
                "detected": 0,
            }

    rows: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    for index, node in enumerate(root.iter()):
        if _local(node.tag).upper() != "STMTTRN":
            continue
        fields = {_local(child.tag).upper(): (child.text or "").strip() for child in list(node)}
        posted = _parse_date(fields.get("DTPOSTED") or fields.get("DTUSER") or "")
        amount = _parse_amount(fields.get("TRNAMT"))
        if not posted or amount is None or amount == 0:
            rejects.append({"index": index, "reason": "Incomplete OFX transaction", "row": fields})
            continue
        description = (
            fields.get("NAME")
            or fields.get("MEMO")
            or fields.get("PAYEE")
            or "Imported transaction"
        )
        rows.append(
            _row_from_mapped(
                posted_on=posted,
                description=description,
                amount=amount,
                account_name=account_name,
                scope=scope,
                external_id=fields.get("FITID") or "",
            )
        )
    return {
        "format": "ofx",
        "headers": [],
        "column_mapping": {
            "posted_on": "DTPOSTED",
            "description": "NAME/MEMO",
            "amount": "TRNAMT",
        },
        "rows": rows,
        "rejects": rejects,
        "detected": len(rows) + len(rejects),
    }


def parse_qif_text(
    text: str,
    *,
    account_name: str,
    scope: str = "personal",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    current: dict[str, str] = {}
    index = 0

    def flush() -> None:
        nonlocal index, current
        if not current:
            return
        posted = _parse_date(current.get("D", ""))
        amount = _parse_amount(current.get("T") or current.get("U"))
        description = (
            current.get("P") or current.get("M") or current.get("N")
            or "Imported transaction"
        )
        if not posted or amount is None or amount == 0:
            rejects.append(
                {"index": index, "reason": "Incomplete QIF transaction", "row": dict(current)}
            )
        else:
            rows.append(
                _row_from_mapped(
                    posted_on=posted,
                    description=description,
                    amount=amount,
                    account_name=account_name,
                    scope=scope,
                )
            )
        index += 1
        current = {}

    for line in text.splitlines():
        if not line:
            continue
        if line.startswith("!"):
            continue
        if line.strip() == "^":
            flush()
            continue
        current[line[0]] = line[1:].strip()
    flush()
    return {
        "format": "qif",
        "headers": [],
        "column_mapping": {"posted_on": "D", "description": "P/M", "amount": "T"},
        "rows": rows,
        "rejects": rejects,
        "detected": len(rows) + len(rejects),
    }


def parse_statement_bytes(
    content: bytes,
    filename: str,
    *,
    account_name: str,
    scope: str = "personal",
    column_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    name = (filename or "").lower()
    text = content.decode("utf-8-sig", errors="replace")
    if name.endswith((".ofx", ".qfx")) or "<OFX" in text.upper()[:2000]:
        return parse_ofx_text(text, account_name=account_name, scope=scope)
    if name.endswith(".qif") or text.lstrip().startswith("!Type:"):
        return parse_qif_text(text, account_name=account_name, scope=scope)
    return parse_csv_text(
        text,
        account_name=account_name,
        scope=scope,
        column_mapping=column_mapping,
    )
