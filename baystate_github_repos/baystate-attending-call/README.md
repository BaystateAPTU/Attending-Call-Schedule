# Baystate Psychiatry — Attending Call Scheduler

Web app for generating the Baystate Psychiatry attending call schedule.
Built with [Streamlit](https://streamlit.io).

## Features
- **Generate** — randomized M–F attending call schedule for 1–12 months
- **Calendar view** — color-coded per attending
- **Attendings** — add, edit, deactivate
- **No-Call Requests** — per-attending calendar toggle
- **Program No-Call Days** — days with no assignment
- **Excel export** — formatted calendar + summary sheet

## Scheduling rules
- Weekdays only (Mon–Fri), 1 attending per day
- Max once per week per attending
- Days distributed as evenly as possible across the pool
- When someone has multiple days in a month, specific days are randomized
- No-call requests honored

## Attendings (initial roster)
Stuart Anfang, Bruce Waslick, Sonia Riyaz, Flannery Merideth, Jennifer Sharma,
Casey Lenderman, Deepika Sundararaj, Faith Donaghey, Sarah Slabaugh, Zachary Herrmann,
Kevin Hill, Stephanie Daly, Hossain Khan, Brianne Kumar

## Deploy to Streamlit Cloud (free)

1. Upload this folder to a GitHub repo (can be private)
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select repo → main file: `app.py` → **Deploy**
4. Share the URL with your team

## Run locally

```bash
pip install streamlit openpyxl
streamlit run app.py
```

## Saving config changes

Changes made in the app live in the browser session only.
To save permanently: **sidebar → 💾 Config → ⬇ Download config**, then replace
`config.json` in this repo and commit.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit application |
| `config.json` | Attending roster and no-call data |
| `requirements.txt` | Python dependencies |
