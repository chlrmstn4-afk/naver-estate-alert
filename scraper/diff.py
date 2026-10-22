def diff_snapshot(previous: dict, current: dict):
    """article_no -> dict 형태의 두 스냅샷을 비교.

    반환: new(신규), changed(가격변동), closed(소멸) 리스트
    """
    new, changed, closed = [], [], []

    for no, item in current.items():
        prev = previous.get(no)
        if prev is None:
            new.append(item)
        elif prev.get("price_man") != item.get("price_man"):
            changed.append({
                "article_no": no,
                "old_price_man": prev.get("price_man"),
                "new_price_man": item.get("price_man"),
                "item": item,
            })

    for no, item in previous.items():
        if no not in current:
            closed.append(item)

    return new, changed, closed


def format_price(man: int) -> str:
    eok, rest = divmod(man, 10000)
    if eok and rest:
        return f"{eok}억 {rest:,}"
    if eok:
        return f"{eok}억"
    return f"{rest:,}만"


def build_summary_lines(complex_name: str, new, changed, closed, watched_areas=None):
    def area_ok(item):
        if not watched_areas:
            return True
        a = item.get("area_exclusive_m2", 0)
        return any(lo <= a <= hi for lo, hi in watched_areas)

    new = [x for x in new if area_ok(x)]
    changed = [x for x in changed if area_ok(x["item"])]
    closed = [x for x in closed if area_ok(x)]

    if not (new or changed or closed):
        return None

    lines = [f"[{complex_name}]"]
    for x in new[:5]:
        lines.append(f"신규 {format_price(x['price_man'])} ({x.get('floor_info','')})")
    for x in changed[:5]:
        lines.append(
            f"가격변동 {format_price(x['old_price_man'])} → {format_price(x['new_price_man'])}"
        )
    for x in closed[:5]:
        lines.append(f"소멸 {format_price(x['price_man'])} ({x.get('floor_info','')})")

    extra = (len(new) + len(changed) + len(closed)) - 15
    if extra > 0:
        lines.append(f"...외 {extra}건")

    return "\n".join(lines)
