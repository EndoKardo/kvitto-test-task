from app.constants import PROMO_CODE, PROMO_DISCOUNT_PERCENT


class UnknownPromoCodeError(ValueError):
    pass


def calc_discount(price: int, promo_code: str | None) -> int:
    if promo_code is None or promo_code.strip() == "":
        return 0
    if promo_code.strip().upper() != PROMO_CODE:
        raise UnknownPromoCodeError(promo_code)
    return price * PROMO_DISCOUNT_PERCENT // 100


def calc_amount(price: int, discount: int) -> int:
    return price - discount


def build_schedule(amount: int, months: int) -> list[int]:
    base, extra = divmod(amount, months)
    # лишние копейки — в первые платежи
    return [base + 1] * extra + [base] * (months - extra)
