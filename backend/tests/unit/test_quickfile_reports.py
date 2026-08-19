"""Unit tests for QuickFile P&L and balance sheet report parsing."""

import pytest

from app.integrations.quickfile_reports import (
    parse_balance_sheet_full,
    parse_profit_and_loss_full,
)

PL_FIXTURE = {
    "Totals": {
        "Turnover": 50000.0,
        "LessCostofSales": -12000.0,
        "LessExpenses": -18000.0,
        "NetProfit": 20000.0,
    },
    "Breakdown": {
        "Turnover": {
            "Balances": {
                "Balance": [
                    {
                        "NominalCode": 4000,
                        "NominalAccountName": "Sales",
                        "Amount": 45000.0,
                    },
                    {
                        "NominalCode": 4001,
                        "NominalAccountName": "Other income",
                        "Amount": 5000.0,
                    },
                ]
            }
        },
        "LessCostofSales": {
            "Balances": {
                "Balance": {
                    "NominalCode": 5000,
                    "NominalAccountName": "Purchases",
                    "Amount": -12000.0,
                }
            }
        },
        "LessExpenses": {
            "Balances": {
                "Balance": [
                    {
                        "NominalCode": 7000,
                        "NominalAccountName": "Rent",
                        "Amount": -10000.0,
                    },
                    {
                        "NominalCode": 7100,
                        "NominalAccountName": "Insurance",
                        "Amount": -8000.0,
                    },
                ]
            }
        },
    },
}

BS_FIXTURE = {
    "Totals": {
        "FixedAssets": 15000.0,
        "CurrentAssets": 25000.0,
        "CurrentLiabilities": -8000.0,
        "LongTermLiabilities": -12000.0,
        "CapitalAndReserves": 20000.0,
    },
    "Breakdown": {
        "FixedAssets": {
            "Balances": {
                "Balance": {
                    "NominalCode": "1000",
                    "NominalAccountName": "Plant and machinery",
                    "Amount": 15000.0,
                }
            }
        },
        "CurrentAssets": {
            "Balances": {
                "Balance": [
                    {
                        "NominalCode": 1200,
                        "NominalAccountName": "Debtors control account",
                        "Amount": 8883.0,
                    },
                    {
                        "NominalCode": 1210,
                        "NominalAccountName": "Vat Account",
                        "Amount": 0.47,
                    },
                    {
                        "NominalCode": 1201,
                        "NominalAccountName": "Bank current account",
                        "Amount": 16117.0,
                    },
                ]
            }
        },
        "CurrentLiabilities": {
            "Balances": {
                "Balance": [
                    {
                        "NominalCode": 2200,
                        "NominalAccountName": "Creditors control account",
                        "Amount": -5000.0,
                    },
                    {
                        "NominalCode": 2201,
                        "NominalAccountName": "Sales Tax Control Account",
                        "Amount": -872.86,
                    },
                    {
                        "NominalCode": 2202,
                        "NominalAccountName": "VAT liability",
                        "Amount": -3000.0,
                    },
                ]
            }
        },
        "LongTermLiabilities": {
            "Balances": {
                "Balance": {
                    "NominalCode": 2300,
                    "NominalAccountName": "Bank loan",
                    "Amount": -12000.0,
                }
            }
        },
        "CapitalAndReserves": {
            "Balances": {
                "Balance": {
                    "NominalCode": 3000,
                    "NominalAccountName": "Share capital",
                    "Amount": 20000.0,
                }
            }
        },
    },
}


def test_parse_profit_and_loss_full_extracts_all_lines_and_subtotals() -> None:
    result = parse_profit_and_loss_full(PL_FIXTURE, from_date="2026-01-01", to_date="2026-01-31")

    assert result["turnover_gbp"] == 50000.0
    assert result["cost_of_sales_gbp"] == 12000.0
    assert result["net_profit_gbp"] == 20000.0

    sections = result["sections"]
    assert len(sections) == 5

    turnover = sections[0]
    assert turnover["key"] == "Turnover"
    assert len(turnover["lines"]) == 2
    assert turnover["lines"][0]["nominal_code"] == "4000"
    assert turnover["lines"][0]["label"] == "Sales"
    assert turnover["lines"][0]["amount_gbp"] == 45000.0
    assert turnover["subtotal_gbp"] == 50000.0

    cos = sections[1]
    assert cos["key"] == "LessCostofSales"
    assert len(cos["lines"]) == 1
    assert cos["lines"][0]["amount_gbp"] == 12000.0

    gross = sections[2]
    assert gross["key"] == "GrossProfit"
    assert gross["subtotal_gbp"] == 38000.0

    expenses = sections[3]
    assert expenses["key"] == "LessExpenses"
    assert len(expenses["lines"]) == 2
    assert expenses["lines"][1]["label"] == "Insurance"

    net = sections[4]
    assert net["key"] == "NetProfit"
    assert net["is_total"] is True
    assert net["subtotal_gbp"] == 20000.0


def test_parse_balance_sheet_full_extracts_all_lines() -> None:
    result = parse_balance_sheet_full(BS_FIXTURE, to_date="2026-01-31")

    assert result["debtors_gbp"] == 8883.0
    assert result["vat_reserve_gbp"] == 0.47
    assert result["vat_liability_gbp"] == 3872.86
    assert result["current_liabilities_gbp"] == 8000.0

    sections = result["sections"]
    assert len(sections) == 5

    fixed = sections[0]
    assert fixed["key"] == "FixedAssets"
    assert fixed["lines"][0]["nominal_code"] == "1000"

    current_assets = sections[1]
    assert len(current_assets["lines"]) == 3

    current_liabilities = sections[2]
    assert current_liabilities["label"] == "Creditors: amounts falling due within one year"
    assert len(current_liabilities["lines"]) == 3

    capital = sections[4]
    assert capital["is_total"] is True
    assert capital["subtotal_gbp"] == 20000.0


def test_parse_balance_sheet_rehomes_misfiled_liability_nominals() -> None:
    """Live QuickFile sometimes lists 2100 creditors / 2300 loans under Current assets."""
    body = {
        "Totals": {
            "FixedAssets": 0.0,
            "CurrentAssets": 30000.0,
            "CurrentLiabilities": 0.0,
            "LongTermLiabilities": 0.0,
            "CapitalAndReserves": 30000.0,
        },
        "Breakdown": {
            "CurrentAssets": {
                "Balances": {
                    "Balance": [
                        {
                            "NominalCode": 1201,
                            "NominalAccountName": "Bank current account",
                            "Amount": 801.73,
                        },
                        {
                            "NominalCode": 2100,
                            "NominalAccountName": "Creditors Control Account",
                            "Amount": 2342.43,
                        },
                        {
                            "NominalCode": 2300,
                            "NominalAccountName": "Loans",
                            "Amount": 26855.84,
                        },
                    ]
                }
            },
            "CurrentLiabilities": {"Balances": {"Balance": []}},
            "LongTermLiabilities": {"Balances": {"Balance": []}},
            "CapitalAndReserves": {
                "Balances": {
                    "Balance": {
                        "NominalCode": 3000,
                        "NominalAccountName": "Share capital",
                        "Amount": 30000.0,
                    }
                }
            },
        },
    }
    result = parse_balance_sheet_full(body, to_date="2026-08-19")
    by_key = {section["key"]: section for section in result["sections"]}
    asset_labels = [line["label"] for line in by_key["CurrentAssets"]["lines"]]
    assert asset_labels == ["Bank current account"]
    assert "Creditors Control Account" not in asset_labels
    assert "Loans" not in asset_labels
    assert by_key["CurrentAssets"]["subtotal_gbp"] == 801.73

    current_liab_labels = [line["label"] for line in by_key["CurrentLiabilities"]["lines"]]
    assert "Creditors Control Account" in current_liab_labels
    assert result["creditors_gbp"] == 2342.43

    long_labels = [line["label"] for line in by_key["LongTermLiabilities"]["lines"]]
    assert "Loans" in long_labels
    assert by_key["LongTermLiabilities"]["subtotal_gbp"] == 26855.84


def test_normalize_live_stored_balance_sheet_rehoms_2100_and_2300() -> None:
    """Stored reports (what /finance/reports serves) keep pre-rehome sections until read.

    Live production shape: Current assets still lists 2100/2300 while creditors within
    one year only has other nominals — the PR #24 parse-time fix never ran on this JSON.
    """
    from app.integrations.quickfile_reports import normalize_parsed_balance_sheet

    # Inflated current assets: true assets (~8572) + 2100 + 2300 ≈ 37770.47
    stored = {
        "to_date": "2026-08-19",
        "fixed_assets_gbp": 0.0,
        "current_assets_gbp": 37770.47,
        "current_liabilities_gbp": 45662.43,
        "long_term_liabilities_gbp": 0.0,
        "capital_and_reserves_gbp": 0.0,
        "debtors_gbp": 0.0,
        "creditors_gbp": 0.0,
        "vat_reserve_gbp": 0.0,
        "vat_liability_gbp": 0.0,
        "sections": [
            {
                "key": "FixedAssets",
                "label": "Fixed assets",
                "lines": [],
                "subtotal_gbp": 0.0,
                "is_total": False,
            },
            {
                "key": "CurrentAssets",
                "label": "Current assets",
                "lines": [
                    {
                        "nominal_code": "1200",
                        "label": "Debtors Control Account",
                        "amount_gbp": 5000.0,
                    },
                    {
                        "nominal_code": "1210",
                        "label": "Vat Account",
                        "amount_gbp": 0.2,
                    },
                    {
                        "nominal_code": "1250",
                        "label": "Petty cash",
                        "amount_gbp": 3572.0,
                    },
                    {
                        "nominal_code": "2100",
                        "label": "Creditors Control Account",
                        "amount_gbp": 2342.43,
                    },
                    {
                        "nominal_code": "2300",
                        "label": "Loans",
                        "amount_gbp": 26855.84,
                    },
                ],
                "subtotal_gbp": 37770.47,
                "is_total": False,
            },
            {
                "key": "CurrentLiabilities",
                "label": "Creditors: amounts falling due within one year",
                "lines": [
                    {"nominal_code": "50", "label": "HP Finance", "amount_gbp": 1000.0},
                    {
                        "nominal_code": "1201",
                        "label": "Director's Loan",
                        "amount_gbp": 5000.0,
                    },
                    {"nominal_code": "2200", "label": "VAT Liability", "amount_gbp": 2000.0},
                    {
                        "nominal_code": "2202",
                        "label": "Corporation Tax",
                        "amount_gbp": 37662.43,
                    },
                ],
                "subtotal_gbp": 45662.43,
                "is_total": False,
            },
            {
                "key": "LongTermLiabilities",
                "label": "Creditors: amounts falling due after one year",
                "lines": [],
                "subtotal_gbp": 0.0,
                "is_total": False,
            },
            {
                "key": "CapitalAndReserves",
                "label": "Capital and reserves",
                "lines": [],
                "subtotal_gbp": 0.0,
                "is_total": True,
            },
        ],
    }

    result = normalize_parsed_balance_sheet(stored)
    by_key = {section["key"]: section for section in result["sections"]}
    asset_codes = [line["nominal_code"] for line in by_key["CurrentAssets"]["lines"]]
    assert "2100" not in asset_codes
    assert "2300" not in asset_codes
    assert asset_codes == ["1200", "1210", "1250"]
    assert result["current_assets_gbp"] == pytest.approx(8572.2)
    assert by_key["CurrentAssets"]["subtotal_gbp"] == pytest.approx(8572.2)

    current_codes = [line["nominal_code"] for line in by_key["CurrentLiabilities"]["lines"]]
    assert "2100" in current_codes
    assert result["creditors_gbp"] == 2342.43
    assert result["current_liabilities_gbp"] == pytest.approx(45662.43 + 2342.43)

    long_codes = [line["nominal_code"] for line in by_key["LongTermLiabilities"]["lines"]]
    assert long_codes == ["2300"]
    assert result["long_term_liabilities_gbp"] == 26855.84


def test_normalize_handles_zero_padded_nominal_codes() -> None:
    from app.integrations.quickfile_reports import normalize_parsed_balance_sheet

    stored = {
        "to_date": "2026-08-19",
        "fixed_assets_gbp": 0.0,
        "current_assets_gbp": 100.0,
        "current_liabilities_gbp": 0.0,
        "long_term_liabilities_gbp": 0.0,
        "capital_and_reserves_gbp": 0.0,
        "sections": [
            {
                "key": "CurrentAssets",
                "label": "Current assets",
                "lines": [
                    {
                        "nominal_code": "02100",
                        "label": "Creditors Control Account",
                        "amount_gbp": 50.0,
                    },
                    {
                        "nominal_code": "02300",
                        "label": "Loans",
                        "amount_gbp": 50.0,
                    },
                ],
                "subtotal_gbp": 100.0,
            },
            {
                "key": "CurrentLiabilities",
                "label": "Creditors: amounts falling due within one year",
                "lines": [],
                "subtotal_gbp": 0.0,
            },
            {
                "key": "LongTermLiabilities",
                "label": "Creditors: amounts falling due after one year",
                "lines": [],
                "subtotal_gbp": 0.0,
            },
        ],
    }
    result = normalize_parsed_balance_sheet(stored)
    by_key = {section["key"]: section for section in result["sections"]}
    assert by_key["CurrentAssets"]["lines"] == []
    assert by_key["CurrentLiabilities"]["lines"][0]["label"] == "Creditors Control Account"
    assert by_key["LongTermLiabilities"]["lines"][0]["label"] == "Loans"


def test_parse_profit_and_loss_full_handles_empty_breakdown() -> None:
    result = parse_profit_and_loss_full(
        {
            "Totals": {
                "Turnover": 1000.0,
                "LessCostofSales": 0,
                "LessExpenses": 0,
                "NetProfit": 1000.0,
            }
        },
        from_date="2026-01-01",
        to_date="2026-01-31",
    )
    assert result["sections"][0]["lines"] == []
    assert result["sections"][0]["subtotal_gbp"] == 1000.0
