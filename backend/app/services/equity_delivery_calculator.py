"""Transparent estimates for Indian retail equity-delivery (CNC) trades.

Rates are taken from Zerodha's published charges page as verified on
2026-09-03.  They are deliberately kept in one small module so an update is
auditable when the broker or an exchange changes a charge.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


SOURCE_URL = "https://zerodha.com/charges/#tab-equities"
RATES_VERIFIED_ON = "2026-09-03"
DP_CHARGE_PER_SCRIP = Decimal("15.34")
STT_RATE = Decimal("0.001")  # 0.1% on each delivery buy and sell
STAMP_DUTY_BUY_RATE = Decimal("0.00015")  # 0.015% on buy side
SEBI_RATE = Decimal("0.000001")  # Rs 10 per crore of turnover
IPFT_RATE = Decimal("0.000000001")  # Rs 0.01 per crore of turnover
GST_RATE = Decimal("0.18")
EXCHANGE_TRANSACTION_RATES = {"NSE": Decimal("0.0000307"), "BSE": Decimal("0.0000375")}


def _money(value: Decimal) -> float:
    """Round monetary amounts like a readable estimate, not a contract note."""
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _decimal(value: float | int | str) -> Decimal:
    return Decimal(str(value))


def calculate_equity_delivery(
    buy_price: float,
    sell_price: float,
    quantity: int,
    exchange: str = "NSE",
    include_dp_charge: bool = True,
) -> dict:
    """Calculate a no-leverage CNC trade estimate with an itemised cost breakdown."""
    if buy_price <= 0 or sell_price <= 0:
        raise ValueError("buy_price and sell_price must both be greater than zero")
    if quantity <= 0 or int(quantity) != quantity:
        raise ValueError("quantity must be a whole number greater than zero")
    exchange = exchange.upper()
    if exchange not in EXCHANGE_TRANSACTION_RATES:
        raise ValueError("exchange must be NSE or BSE")

    qty = _decimal(quantity)
    buy_value = _decimal(buy_price) * qty
    sell_value = _decimal(sell_price) * qty
    turnover = buy_value + sell_value
    transaction_charges = turnover * EXCHANGE_TRANSACTION_RATES[exchange]
    sebi_charges = turnover * SEBI_RATE
    ipft_charges = turnover * IPFT_RATE
    brokerage = Decimal("0")
    gst = (brokerage + transaction_charges + sebi_charges + ipft_charges) * GST_RATE
    dp_charges = DP_CHARGE_PER_SCRIP if include_dp_charge else Decimal("0")
    stt = (buy_value + sell_value) * STT_RATE
    stamp_duty = buy_value * STAMP_DUTY_BUY_RATE
    total_charges = brokerage + stt + transaction_charges + sebi_charges + ipft_charges + gst + dp_charges + stamp_duty
    gross_profit = sell_value - buy_value
    net_profit = gross_profit - total_charges

    # The buy-side costs are fixed.  Solve the sell price algebraically so the
    # user can see the actual exit price required to cover all stated charges.
    buy_side_costs = buy_value * (STT_RATE + STAMP_DUTY_BUY_RATE)
    buy_side_costs += buy_value * (EXCHANGE_TRANSACTION_RATES[exchange] + SEBI_RATE + IPFT_RATE) * (Decimal("1") + GST_RATE)
    sell_variable_rate = STT_RATE + (EXCHANGE_TRANSACTION_RATES[exchange] + SEBI_RATE + IPFT_RATE) * (Decimal("1") + GST_RATE)
    break_even_sell_value = (buy_value + buy_side_costs + dp_charges) / (Decimal("1") - sell_variable_rate)
    break_even_sell_price = break_even_sell_value / qty

    return {
        "trade_type": "Equity delivery (CNC)",
        "exchange": exchange,
        "quantity": int(quantity),
        "buy_price": _money(_decimal(buy_price)),
        "sell_price": _money(_decimal(sell_price)),
        "buy_value": _money(buy_value),
        "sell_value": _money(sell_value),
        "turnover": _money(turnover),
        "gross_profit": _money(gross_profit),
        "charges": {
            "brokerage": _money(brokerage),
            "stt": _money(stt),
            "exchange_transaction_charges": _money(transaction_charges),
            "sebi_charges": _money(sebi_charges),
            "ipft_charges": _money(ipft_charges),
            "gst": _money(gst),
            "stamp_duty": _money(stamp_duty),
            "dp_charges": _money(dp_charges),
            "total": _money(total_charges),
        },
        "net_profit": _money(net_profit),
        "net_return_pct": _money((net_profit / buy_value) * Decimal("100")),
        "break_even_sell_price": _money(break_even_sell_price),
        "break_even_sell_value": _money(break_even_sell_value),
        "assumptions": [
            "Retail equity delivery / CNC only; no intraday, futures, options, margin, loan, or AMC charges.",
            "Brokerage is Rs 0 for equity delivery under Zerodha's published retail rate.",
            "DP charge is applied once for this scrip sale, not per share.",
            "This is an estimate. Contract-note rounding and published charges can change.",
        ],
        "fee_source": {"name": "Zerodha published charges", "url": SOURCE_URL, "verified_on": RATES_VERIFIED_ON},
    }
