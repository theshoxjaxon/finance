#!/usr/bin/env python3
"""VaultAI ledger engine. Deterministic math so the model never does arithmetic in its head.

Usage:
  python vault.py add     <profile.json> <ledger.jsonl> '<entry-json>'   # dedupe + append + pace report
  python vault.py pace    <profile.json> <ledger.jsonl> [YYYY-MM-DD]      # pacing for all categories
  python vault.py summary <profile.json> <ledger.jsonl> [YYYY-MM-DD]      # month overview
"""
import json, sys, calendar, datetime as dt
from pathlib import Path

EARLY_FLOOR = 0.25  # expected spend never below 25% of cap -> no false reds in week 1


def load_profile(p):
    return json.loads(Path(p).read_text())


def load_ledger(p):
    path = Path(p)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def fmt(n):
    return f"{int(round(n)):,}".replace(",", " ")


def pace_category(cat, cfg, entries, today):
    days = calendar.monthrange(today.year, today.month)[1]
    month = today.strftime("%Y-%m")
    rows = [e for e in entries if e["category"] == cat and e["date"].startswith(month)]
    spent = sum(e["amount_uzs"] for e in rows)
    cap = cfg["cap"]
    out = {"category": cat, "type": cfg.get("type", "flex"), "spent": spent, "cap": cap,
           "count": len(rows), "day": today.day, "days": days}
    if out["type"] == "fixed":
        out["status"] = "✅ paid" if spent else "⏳ due"
        return out
    expected = max(cap * today.day / days, cap * EARLY_FLOOR)
    ratio = spent / expected if expected else 0
    out["ratio"] = round(ratio, 2)
    out["status"] = "🟢" if ratio <= 1.0 else "🟡" if ratio <= 1.3 else "🔴"
    days_left = days - today.day + 1
    out["left"] = cap - spent
    out["per_day_left"] = max(cap - spent, 0) / days_left
    return out


def line(r):
    base = f"{r['status']} {r['category']}: {fmt(r['spent'])} / {fmt(r['cap'])} UZS (x{r['count']}, day {r['day']}/{r['days']})"
    if r["type"] == "flex":
        base += f" | ratio {r['ratio']} | left {fmt(r['left'])} ≈ {fmt(r['per_day_left'])}/day"
    return base


def find_dupes(entry, entries):
    return [e for e in entries if e["date"] == entry["date"]
            and e["amount_uzs"] == entry["amount_uzs"]
            and e["vendor"].lower() == entry["vendor"].lower()]


def cmd_add(profile_p, ledger_p, raw):
    prof, entries = load_profile(profile_p), load_ledger(ledger_p)
    e = json.loads(raw)
    force = e.pop("_force", False)
    for k in ("date", "vendor", "amount_uzs", "category", "class"):
        if k not in e:
            sys.exit(f"ERROR missing field: {k}")
    if e["category"] not in prof["categories"]:
        sys.exit(f"ERROR unknown category '{e['category']}'. Known: {', '.join(prof['categories'])}")
    dupes = find_dupes(e, entries)
    if dupes and not force:
        print("POSSIBLE_DUPLICATE " + json.dumps(dupes, ensure_ascii=False))
        print("Ask the user. If it is a separate purchase, re-run with \"_force\": true.")
        return
    base = f"{e['date']}-{e['vendor'].lower().replace(' ', '')}-{e['amount_uzs']}"
    n = sum(1 for x in entries if x.get("id", "").startswith(base)) + 1
    e["id"] = f"{base}-{n:02d}"
    e.setdefault("platform", "unknown")
    e.setdefault("original", {"amount": e["amount_uzs"], "currency": "UZS", "fx_rate": None})
    e.setdefault("source", "receipt")
    Path(ledger_p).parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_p, "a") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    entries.append(e)
    today = dt.date.fromisoformat(e["date"])
    print("ADDED " + json.dumps(e, ensure_ascii=False))
    print(line(pace_category(e["category"], prof["categories"][e["category"]], entries, today)))


def cmd_pace(profile_p, ledger_p, date=None):
    prof, entries = load_profile(profile_p), load_ledger(ledger_p)
    today = dt.date.fromisoformat(date) if date else dt.date.today()
    for cat, cfg in prof["categories"].items():
        print(line(pace_category(cat, cfg, entries, today)))


def cmd_summary(profile_p, ledger_p, date=None):
    prof, entries = load_profile(profile_p), load_ledger(ledger_p)
    today = dt.date.fromisoformat(date) if date else dt.date.today()
    month = today.strftime("%Y-%m")
    rows = [e for e in entries if e["date"].startswith(month)]
    total = sum(e["amount_uzs"] for e in rows)
    by_class = {c: sum(e["amount_uzs"] for e in rows if e["class"] == c) for c in ("need", "want", "waste")}
    income, target = prof["monthly_income_uzs"], prof["savings_target_uzs"]
    unpaid_fixed = sum(c["cap"] for k, c in prof["categories"].items()
                       if c.get("type") == "fixed" and not any(e["category"] == k for e in rows))
    # conservative: every category reaches at least its cap by month end
    committed = sum(max(sum(e["amount_uzs"] for e in rows if e["category"] == k), c["cap"])
                    for k, c in prof["categories"].items())
    projected = income - committed
    print(f"MONTH {month} | spent {fmt(total)} UZS | unpaid fixed {fmt(unpaid_fixed)} | income {fmt(income)} | "
          f"projected savings (caps used) {fmt(projected)} vs target {fmt(target)}")
    print("BY CLASS " + " | ".join(f"{k} {fmt(v)}" for k, v in by_class.items()))
    if by_class["waste"]:
        print(f"WASTE = {by_class['waste'] / target * 100:.1f}% of savings target")
    vendors = {}
    for e in rows:
        vendors.setdefault(e["vendor"], [0, 0])
        vendors[e["vendor"]][0] += 1
        vendors[e["vendor"]][1] += e["amount_uzs"]
    top = sorted(vendors.items(), key=lambda kv: -kv[1][0])[:3]
    print("TOP VENDORS " + " | ".join(f"{v} x{c} = {fmt(s)}" for v, (c, s) in top))
    cmd_pace(profile_p, ledger_p, today.isoformat())


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cmd, *args = sys.argv[1:]
    {"add": cmd_add, "pace": cmd_pace, "summary": cmd_summary}[cmd](*args)
