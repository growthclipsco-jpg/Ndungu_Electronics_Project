"""
TC-14: Monetary Arithmetic & Integer Cents Validation.
Verifies integer-cents representation, Decimal(ROUND_HALF_UP) calculations,
and absence of floating-point rounding drift.
"""

from decimal import Decimal
import pytest
from app.domain.money import (
    Money, to_cents, to_kes, format_kes, calculate_vat, round_half_up
)


def test_tc14_integer_cents_conversion():
    """Validates accurate conversion between KES amounts and integer cents."""
    assert to_cents(1500) == 150000
    assert to_cents("1500.50") == 150050
    assert to_cents(Decimal("14250.75")) == 1425075
    assert to_cents("10.005") == 1001  # ROUND_HALF_UP rounding


def test_tc14_to_kes_decimal():
    """Validates accurate decimal representation."""
    assert to_kes(1425000) == Decimal("14250.00")
    assert to_kes(150) == Decimal("1.50")
    assert to_kes(5) == Decimal("0.05")


def test_tc14_format_kes():
    """Validates currency formatting matching Thika Daylight monospace spec."""
    assert format_kes(1425000) == "KES 14,250.00"
    assert format_kes(489240000) == "KES 4,892,400.00"
    assert format_kes(50, include_symbol=False) == "0.50"
    assert format_kes(-150000) == "KES -1,500.00"


def test_tc14_vat_calculation_locked_policy():
    """
    Validates locked VAT policy (+16% on post-discount subtotal).
    Formula: tax_cents = round_half_up(discounted_subtotal * 0.16).
    """
    # 10,000 KES (1,000,000 cents) -> 1,600 KES (160,000 cents)
    assert calculate_vat(1000000) == 160000

    # 15,250.50 KES (1,525,050 cents) * 0.16 = 244,008 cents
    assert calculate_vat(1525050) == 244008

    # Zero subtotal
    assert calculate_vat(0) == 0


def test_tc14_money_arithmetic_and_immutability():
    """Validates Money value object arithmetic and immutability."""
    m1 = Money.from_kes("100.00")
    m2 = Money.from_kes("50.25")

    m_sum = m1 + m2
    assert m_sum.cents == 15025
    assert str(m_sum) == "KES 150.25"

    m_diff = m1 - m2
    assert m_diff.cents == 4975
    assert str(m_diff) == "KES 49.75"

    # Multiplication with integer quantity
    m_qty = m2 * 3
    assert m_qty.cents == 15075

    # Comparisons
    assert m1 > m2
    assert m2 < m1
    assert Money(1000) == Money(1000)
    assert Money(1000) == 1000

    # Immutability
    with pytest.raises(AttributeError):
        m1._cents = 20000


def test_tc14_no_float_storage_in_db(app):
    """Verifies SQLite column affinity for prices is strictly INTEGER."""
    from app.db import get_db
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("PRAGMA table_info(products)")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}

        assert columns["price_cents"] == "INTEGER"
        assert columns["cost_price_cents"] == "INTEGER"
        assert "price" not in columns  # Old legacy float column must not exist
