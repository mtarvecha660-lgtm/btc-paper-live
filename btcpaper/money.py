def inr_group(x):
    """Indian digit grouping: 1234567.8 -> '12,34,567.80'."""
    neg = x < 0
    s = f"{abs(x):.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return ("-" if neg else "") + whole + "." + frac


def money(usdt, inr_rate=None, sign=False):
    if abs(usdt) < 0.005:
        usdt = 0.0                       # no "-0.00"
    s = f"{usdt:+,.2f}" if sign else f"{usdt:,.2f}"
    out = f"{s} USDT"
    if inr_rate:
        v = usdt * inr_rate
        out += f" (~Rs {'+' if sign and v >= 0 else ''}{inr_group(v)})"
    return out
