"""
Domain model for Money arithmetic and Kenyan Shillings (KES) formatting.
Enforces integer-cents representation and Decimal ROUND_HALF_UP arithmetic.
Zero floating-point rounding drift.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

VAT_RATE = Decimal('0.16')


def round_half_up(value: Union[Decimal, float, str]) -> int:
    """Rounds a Decimal value to nearest integer cent using ROUND_HALF_UP."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def to_cents(amount: Union[str, int, float, Decimal]) -> int:
    """
    Converts a KES currency representation (e.g. 1500, 1500.50, '1500.50') to integer cents.
    1 KES = 100 cents.
    """
    if isinstance(amount, int):
        return amount * 100
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount).strip())
    cents = (amount * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return int(cents)


def to_kes(cents: int) -> Decimal:
    """Converts integer cents to a 2-decimal-place Decimal KES amount."""
    if not isinstance(cents, int):
        raise TypeError(f"cents must be an integer, got {type(cents).__name__}")
    return (Decimal(cents) / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def format_kes(cents: int, include_symbol: bool = True) -> str:
    """
    Formats integer cents into standard Kenyan Shillings string representation.
    Example: 1425000 cents -> 'KES 14,250.00' (or '14,250.00' if include_symbol=False).
    """
    if not isinstance(cents, int):
        raise TypeError(f"cents must be an integer, got {type(cents).__name__}")
    is_neg = cents < 0
    abs_cents = abs(cents)
    shillings = abs_cents // 100
    remainder = abs_cents % 100
    formatted = f"{shillings:,}.{remainder:02d}"
    if is_neg:
        formatted = f"-{formatted}"
    return f"KES {formatted}" if include_symbol else formatted


def calculate_vat(discounted_subtotal_cents: int, rate: Decimal = VAT_RATE) -> int:
    """
    Calculates +16% VAT on top of post-discount subtotal in integer cents.
    tax_cents = round_half_up(discounted_subtotal_cents * rate)
    """
    if discounted_subtotal_cents <= 0:
        return 0
    return round_half_up(Decimal(discounted_subtotal_cents) * rate)


class Money:
    """
    Immutable value object representing monetary amounts in integer cents.
    Prevents floating point errors and provides strict domain arithmetic.
    """
    __slots__ = ('_cents',)

    def __init__(self, cents: int = 0):
        if not isinstance(cents, int):
            raise TypeError(f"cents must be an integer, got {type(cents).__name__}")
        object.__setattr__(self, '_cents', cents)

    @classmethod
    def from_kes(cls, amount: Union[str, int, float, Decimal]) -> 'Money':
        """Factory constructor from KES amount."""
        return cls(to_cents(amount))

    @classmethod
    def from_cents(cls, cents: int) -> 'Money':
        """Factory constructor from integer cents."""
        return cls(cents)

    @classmethod
    def zero(cls) -> 'Money':
        return cls(0)

    @property
    def cents(self) -> int:
        return self._cents

    @property
    def kes(self) -> Decimal:
        return to_kes(self._cents)

    def format(self, include_symbol: bool = True) -> str:
        return format_kes(self._cents, include_symbol)

    def calculate_vat(self, rate: Decimal = VAT_RATE) -> 'Money':
        return Money(calculate_vat(self._cents, rate))

    def __setattr__(self, key, value):
        raise AttributeError("Money is immutable")

    def __repr__(self) -> str:
        return f"Money({self._cents} cents, {self.format()})"

    def __str__(self) -> str:
        return self.format()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self._cents == other._cents
        if isinstance(other, int):
            return self._cents == other
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self._cents < other._cents
        if isinstance(other, int):
            return self._cents < other
        raise TypeError(f"Cannot compare Money with {type(other).__name__}")

    def __le__(self, other: object) -> bool:
        return self < other or self == other

    def __gt__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self._cents > other._cents
        if isinstance(other, int):
            return self._cents > other
        raise TypeError(f"Cannot compare Money with {type(other).__name__}")

    def __ge__(self, other: object) -> bool:
        return self > other or self == other

    def __add__(self, other: object) -> 'Money':
        if isinstance(other, Money):
            return Money(self._cents + other._cents)
        if isinstance(other, int):
            return Money(self._cents + other)
        raise TypeError(f"Cannot add {type(other).__name__} to Money")

    def __sub__(self, other: object) -> 'Money':
        if isinstance(other, Money):
            return Money(self._cents - other._cents)
        if isinstance(other, int):
            return Money(self._cents - other)
        raise TypeError(f"Cannot subtract {type(other).__name__} from Money")

    def __mul__(self, other: Union[int, Decimal, float]) -> 'Money':
        if isinstance(other, int):
            return Money(self._cents * other)
        if isinstance(other, (Decimal, float)):
            dec = Decimal(str(other))
            return Money(round_half_up(Decimal(self._cents) * dec))
        raise TypeError(f"Cannot multiply Money by {type(other).__name__}")

    def __rmul__(self, other: Union[int, Decimal, float]) -> 'Money':
        return self.__mul__(other)

    def __neg__(self) -> 'Money':
        return Money(-self._cents)

    def __pos__(self) -> 'Money':
        return self

    def __abs__(self) -> 'Money':
        return Money(abs(self._cents))

    def __bool__(self) -> bool:
        return self._cents != 0
