from enum import StrEnum

PROMO_CODE = "KVITTO10"
PROMO_DISCOUNT_PERCENT = 10


class PaymentMethod(StrEnum):
    CARD = "card"
    SBP = "sbp"
    INSTALLMENT = "installment"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


ALLOWED_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset(
        {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}
    ),
    PaymentStatus.SUCCEEDED: frozenset({PaymentStatus.REFUNDED}),
}

INSTALLMENT_MONTHS: frozenset[int] = frozenset({3, 6, 12})

# (title, price_kopecks)
TARIFFS: tuple[tuple[str, int], ...] = (
    ("basic", 990_000),
    ("standard", 1_990_000),
    ("premium", 2_990_000),
)
