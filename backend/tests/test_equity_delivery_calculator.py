import pytest

from app.services.equity_delivery_calculator import calculate_equity_delivery


def test_equity_delivery_calculator_itemises_zero_brokerage_and_dp_charge():
    result = calculate_equity_delivery(100, 110, 10, "NSE")

    assert result["trade_type"] == "Equity delivery (CNC)"
    assert result["buy_value"] == 1000.0
    assert result["sell_value"] == 1100.0
    assert result["gross_profit"] == 100.0
    assert result["charges"]["brokerage"] == 0.0
    assert result["charges"]["dp_charges"] == 15.34
    assert result["net_profit"] < result["gross_profit"]
    assert result["break_even_sell_price"] > 100


def test_bse_rate_and_optional_dp_charge_are_supported():
    without_dp = calculate_equity_delivery(100, 110, 10, "BSE", include_dp_charge=False)
    with_dp = calculate_equity_delivery(100, 110, 10, "BSE", include_dp_charge=True)

    assert without_dp["charges"]["dp_charges"] == 0.0
    assert with_dp["net_profit"] == pytest.approx(without_dp["net_profit"] - 15.34)
    assert with_dp["charges"]["exchange_transaction_charges"] > 0


@pytest.mark.parametrize("buy,sell,quantity", [(0, 100, 1), (100, -1, 1), (100, 101, 0), (100, 101, 1.5)])
def test_equity_delivery_calculator_rejects_invalid_inputs(buy, sell, quantity):
    with pytest.raises(ValueError):
        calculate_equity_delivery(buy, sell, quantity)
