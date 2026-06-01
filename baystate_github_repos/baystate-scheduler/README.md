# Baystate Psychiatry — Resident Call Scheduler

Web app for generating and managing the Baystate Psychiatry residency call schedule (2026–2027).
Built with [Streamlit](https://streamlit.io).

## Live app
Deploy your own instance — see **Deploy** below.

## Features
- **Generate** — produce 1–12 months of call schedule at once
- **Calendar view** — color-coded by shift type (weekday UL, weekend APTU/consult, intern, jeopardy)
- **Residents** — add, edit, deactivate; set away periods and blocked rotations
- **Holidays** — calendar view of pre-assigned locked holiday coverage
- **No-Call Requests** — per-resident calendar toggle
- **Program No-Call Days** — retreats, in-service exam, graduation
- **Excel export** — formatted multi-sheet workbook with call counts summary

## Scheduling rules

| Rule | Detail |
|------|--------|
| Weekday coverage | 1 upper-level (PGY-2+) overnight; optional intern (9a–5p) if UL is PGY-3/4 |
| Weekend coverage | APTU (PGY-3/4) + Consult (PGY-3/4); intern day shift with ramp-up limits |
| Intern ramp-up | July: 2 weekdays · Aug–Sep: +1 weekend · Oct+: 2 weekdays + 2 weekends |
| Q-frequency | q5 preferred (gap ≥ 4 days), q4 acceptable, q3 flagged for manual review |
| Monthly caps | PGY-2: soft 5/hard 6 · PGY-3: soft 3/hard 5 · PGY-4: soft 2/hard 4 |
| Holidays | Pre-assigned and locked; 3-day buffer before holiday shifts |
| PGY-1 blocks | Not eligible during Medicine Wards, Emergency Medicine, Neurology |
| Wed/Fri equity | Scoring penalty for residents with disproportionate Wed/Fri load |

## Deploy to Streamlit Cloud (free)

1. Upload this folder to a GitHub repo (can be private)
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select repo → main file: `app.py` → **Deploy**
4. Share the URL with your team

To restrict access: Streamlit Cloud settings → **Sharing** → add email addresses.

## Run locally

```bash
pip install streamlit openpyxl
streamlit run app.py
```

## Saving config changes

Changes made in the app live in the browser session only.
To save permanently: **sidebar → 💾 Config → ⬇ Download config.json**, then replace
`config.json` in this repo and commit.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit application |
| `config.json` | Resident roster, holidays, no-call requests, program no-call days |
| `requirements.txt` | Python dependencies |
