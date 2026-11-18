# Formátování dat (česky / anglicky podle texts.LANG) bez závislosti na systémovém locale.
from . import texts

DNY = ("po", "út", "st", "čt", "pá", "so", "ne")
DAYS_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _lang(lang):
    return lang or texts.LANG


def short_date(d, lang=None):
    """„18. 11.“ / „Nov 18“."""
    if _lang(lang) == "en":
        return f"{MONTHS_EN[d.month - 1]} {d.day}"
    return f"{d.day}. {d.month}."


def weekday_date(d, lang=None):
    """„st 18. 11.“ / „Wed Nov 18“."""
    days = DAYS_EN if _lang(lang) == "en" else DNY
    return f"{days[d.weekday()]} {short_date(d, lang)}"


def full_date(d, lang=None):
    """„st 18. 11. 2026“ / „Wed Nov 18, 2026“."""
    sep = ", " if _lang(lang) == "en" else " "
    return f"{weekday_date(d, lang)}{sep}{d.year}"


def later_date(d, today):
    """Datum v sekci Další dny; v jiném roce i s rokem."""
    return weekday_date(d) if d.year == today.year else full_date(d)


def day_heading(d, today):
    base = weekday_date(d)
    delta = (d - today).days
    if delta == 0:
        return f"{texts.TODAY} · {base}"
    if delta == 1:
        return f"{texts.TOMORROW} · {base}"
    return base


def bar_label(label, counts):
    today = counts.get("today", 0)
    overdue = counts.get("overdue", 0)
    text = f"{label} {today}" if label is not None else str(today)  # bez popisku jen počty
    return (text, f"⚠{overdue}" if overdue else None,
            today == 0 and overdue == 0)
