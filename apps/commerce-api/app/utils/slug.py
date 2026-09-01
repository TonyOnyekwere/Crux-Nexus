import re
import unicodedata


def normalize_storefront_slug(value: str, *, max_length: int = 50, separator: str = "-") -> str:
    """Normalize a storefront slug to a safe lowercase, hyphen-delimited identifier."""
    if value is None:
        raise ValueError("Storefront slug is required")

    text = str(value).strip()
    if not text:
        raise ValueError("Storefront slug is required")

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    replacements = {
        "æ": "ae",
        "œ": "oe",
        "ß": "ss",
        "ø": "o",
        "đ": "d",
        "ł": "l",
        "þ": "th",
        "ı": "i",
        "ð": "d",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = text.lower()
    text = re.sub(r"[_\s/\\.]+", separator, text)
    text = re.sub(r"[^a-z0-9-]+", separator, text)
    text = re.sub(rf"{re.escape(separator)}{{2,}}", separator, text)
    text = text.strip(separator)

    if not text:
        raise ValueError("Storefront slug is required")

    if len(text) > max_length:
        text = text[:max_length].rstrip(separator)

    if not text:
        raise ValueError("Storefront slug is required")

    return text
