import re

from app.core.errors import CommerceError


def explicit_confirmation(message: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:yes(?:,?\s+(?:please|place (?:the |my )?order))?|confirm(?: (?:the )?order)?|place (?:the |my )order)[.!\s]*",
            message.strip(),
            flags=re.IGNORECASE,
        )
    )


def authorize_intent(intent: str, message: str, pending: bool) -> None:
    if intent == "confirm":
        if not pending or not explicit_confirmation(message):
            raise CommerceError(
                "Please review checkout and explicitly confirm before placing an order.", 403
            )
    patterns = {
        "add": r"\b(add|put|buy|take)\b",
        "remove": r"\b(remove|delete|drop)\b",
        "update": r"\b(quantity|change|update|make)\b",
        "checkout": r"\b(checkout|check out)\b",
    }
    if intent in patterns and (
        not re.search(patterns[intent], message, re.I)
        or re.search(r"\b(don't|do not|never)\b", message, re.I)
    ):
        raise CommerceError("Please state the cart action you'd like me to take.", 403)
