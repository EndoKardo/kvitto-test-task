from app.constants import ALLOWED_TRANSITIONS, PaymentStatus


def can_transition(current: PaymentStatus, new: PaymentStatus) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())
