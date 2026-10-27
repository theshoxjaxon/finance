# VaultAI — personal budget & savings strategist

Track monthly income and spending in UZS, see how each category is pacing against its cap, and turn the numbers into a savings plan.

## Web app (`index.html`)

Open `index.html` in a browser — no build step, no dependencies. Or enable **GitHub Pages** (Settings → Pages → `main` / root).

| Tab | What it does |
|---|---|
| **Overview** | Income, spent, bills still due, projected savings vs target, savings rate; pacing bar per category with a "where you should be today" marker |
| **Transactions** | Add expenses or income (UZS / USD / EUR with FX rate), duplicate warning, monthly list |
| **Strategy** | Savings verdict, 50/30/20 check, savings goals with required monthly amount, auto action plan, **BUY / WAIT / PASS** check |
| **Budget setup** | Income, savings target, current savings, category caps (fixed vs flex) and an over-allocation check |
| **Import / Export** | Paste a month as `date, vendor, amount, category, class` lines (use `income` as the category for money in), import/export `.jsonl`, `.csv`, `user_profile.json` |

Data is stored only in your browser (localStorage). Export regularly.

### Paste format
```
2026-10-01, Salary, 12000000, income, need
2026-10-02, Korzinka, 245000, groceries, need
2026-10-03, Yandex Go, 38000, transport, want
2026-10-04, Bellissimo, 250000, dining, waste
```

## Pacing rules
- **class** = what an item is: `need` / `want` / `waste`
- **pacing** (flex categories): `expected = max(cap × day / days_in_month, 25% × cap)`, `ratio = spent / expected` → 🟢 ≤ 1.0 · 🟡 ≤ 1.3 · 🔴 > 1.3
- **fixed** categories (rent, internet) show ✅ paid / ⏳ due instead of a ratio
- Projected savings = income − Σ max(spent, cap) per category (assumes every cap gets used — conservative on purpose)

## CLI engine (`engine/vault.py`)
Same math, used by the VaultAI Claude skill.
```bash
cp engine/user_profile.example.json user_profile.json   # edit with your numbers
python engine/vault.py add user_profile.json ledger/2026-10.jsonl '{"date":"2026-10-02","vendor":"Evos","amount_uzs":100000,"category":"dining","class":"want"}'
python engine/vault.py pace    user_profile.json ledger/2026-10.jsonl
python engine/vault.py summary user_profile.json ledger/2026-10.jsonl
```

## Privacy
`user_profile.json`, `ledger/` and all `.jsonl` / `.csv` files are git-ignored so real financial data never gets committed.
