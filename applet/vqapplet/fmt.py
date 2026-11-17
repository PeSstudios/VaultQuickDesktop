# České formátování bez závislosti na systémovém locale.
from . import texts

DNY = ("po", "út", "st", "čt", "pá", "so", "ne")


def short_date(d):
    return f"{d.day}. {d.month}."


def day_heading(d, today):
    base = f"{DNY[d.weekday()]} {short_date(d)}"
    delta = (d - today).days
    if delta == 0:
        return f"{texts.TODAY} · {base}"
    if delta == 1:
        return f"{texts.TOMORROW} · {base}"
    return base


def bar_label(label, counts):
    today = counts.get("today", 0)
    overdue = counts.get("overdue", 0)
    return (f"{label} {today}", f"⚠{overdue}" if overdue else None,
            today == 0 and overdue == 0)
