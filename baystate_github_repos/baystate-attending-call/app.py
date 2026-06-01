"""
Baystate Psychiatry — Attending Call Scheduler
Streamlit web app · Deploy free at share.streamlit.io
"""

import streamlit as st
import json, os, io, random, calendar
from datetime import date, timedelta
from copy import deepcopy

st.set_page_config(
    page_title="Baystate Attending Call",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# DEFAULT DATA
# ─────────────────────────────────────────────────────────────
DEFAULT_ATTENDINGS = [
    "Stuart Anfang",
    "Bruce Waslick",
    "Sonia Riyaz",
    "Flannery Merideth",
    "Jennifer Sharma",
    "Casey Lenderman",
    "Deepika Sundararaj",
    "Faith Donaghey",
    "Sarah Slabaugh",
    "Zachary Herrmann",
    "Kevin Hill",
    "Stephanie Daly",
    "Hossain Khan",
    "Brianne Kumar",
]

DEFAULT_CONFIG = {
    "attendings": [{"name": n, "active": True, "no_call": []} for n in DEFAULT_ATTENDINGS],
    "program_no_call": [],
}

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "attending_config.json")

def get_cfg():
    if "att_config" not in st.session_state:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                st.session_state.att_config = json.load(f)
        else:
            st.session_state.att_config = deepcopy(DEFAULT_CONFIG)
    return st.session_state.att_config

def save_cfg(cfg):
    st.session_state.att_config = cfg

def active_attendings(cfg):
    return [a for a in cfg["attendings"] if a.get("active", True)]

def is_no_call(name, d, cfg):
    return d.isoformat() in (next((a for a in cfg["attendings"] if a["name"] == name), {}).get("no_call", []))

def is_program_nc(d, cfg):
    return d.isoformat() in cfg.get("program_no_call", [])

# ─────────────────────────────────────────────────────────────
# SCHEDULER
# Rules:
#   • Weekdays only (Mon–Fri)
#   • 1 attending per day
#   • Max 1 call per week per attending
#   • When someone is called multiple times in a month, days randomized
#   • No-call requests honored
#   • Program no-call days skipped
# ─────────────────────────────────────────────────────────────
def schedule_month(year, month, cfg, seed=None):
    rng = random.Random(seed)
    first = date(year, month, 1)
    last  = date(year, month + 1, 1) - timedelta(1) if month < 12 else date(year + 1, 1, 1) - timedelta(1)

    # Collect all eligible weekdays
    weekdays = []
    d = first
    while d <= last:
        if d.weekday() < 5 and not is_program_nc(d, cfg):
            weekdays.append(d)
        d += timedelta(1)

    pool = [a["name"] for a in active_attendings(cfg)]
    n_days = len(weekdays)
    n_att  = len(pool)

    if n_att == 0:
        return {}, ["No active attendings."]

    # ── Build a base distribution ──────────────────────────
    # Divide weekdays as evenly as possible across attendings,
    # then shuffle which days each person gets.
    base, extra = divmod(n_days, n_att)
    # extra attendings get one additional day
    counts = {name: base + (1 if i < extra else 0) for i, name in enumerate(pool)}

    # Shuffle pool so the "extra" days are distributed randomly
    shuffled_pool = pool[:]
    rng.shuffle(shuffled_pool)
    counts = {name: base + (1 if i < extra else 0) for i, name in enumerate(shuffled_pool)}

    # Build the assignment list respecting max-once-per-week
    # Strategy: for each attending who needs k days, pick k days from the calendar
    # such that no two are in the same ISO week.
    iso_week = lambda d: d.isocalendar()[1]

    # Group weekdays by ISO week
    weeks = {}
    for d in weekdays:
        wk = iso_week(d)
        weeks.setdefault(wk, []).append(d)

    # Shuffle within each week for randomness
    for wk in weeks:
        rng.shuffle(weeks[wk])

    sched   = {}   # date → attending name
    warnings = []

    # Assign round-robin across weeks, randomizing attending order each round
    # Each "round" picks one day per attending (from different weeks where possible)
    assigned_weeks = {name: set() for name in shuffled_pool}
    day_pool = list(weekdays)  # all days in order
    rng.shuffle(day_pool)

    # Build eligible days per attending
    def eligible_days(name, days_left):
        """Days this attending can take: no no-call, not already in a week they have."""
        result = []
        for d in days_left:
            if is_no_call(name, d, cfg): continue
            if iso_week(d) in assigned_weeks[name]: continue
            result.append(d)
        return result

    # Assign iteratively: each pass assigns one day to each attending who still needs days
    remaining_days = set(weekdays)
    needed = dict(counts)

    # Multiple passes until everyone is satisfied or no progress possible
    max_passes = n_days + 10
    for _ in range(max_passes):
        if all(v == 0 for v in needed.values()): break
        if not remaining_days: break

        order = [n for n in shuffled_pool if needed[n] > 0]
        rng.shuffle(order)
        progress = False

        for name in order:
            if needed[name] <= 0: continue
            avail = [d for d in sorted(remaining_days) if d not in sched
                     and not is_no_call(name, d, cfg)
                     and iso_week(d) not in assigned_weeks[name]]
            if not avail: continue
            chosen = rng.choice(avail)
            sched[chosen] = name
            assigned_weeks[name].add(iso_week(chosen))
            remaining_days.discard(chosen)
            needed[name] -= 1
            progress = True

        if not progress: break

    # Fill any remaining uncovered days (fallback: relax once-per-week constraint)
    uncovered = [d for d in weekdays if d not in sched and not is_program_nc(d, cfg)]
    if uncovered:
        warnings.append(f"{len(uncovered)} day(s) couldn't be covered with once-per-week constraint — filling with least-loaded attendings.")
        # Count current assignments
        load = {name: sum(1 for v in sched.values() if v == name) for name in pool}
        for d in uncovered:
            avail = [n for n in pool if not is_no_call(n, d, cfg)]
            if not avail: avail = pool
            avail.sort(key=lambda n: load.get(n, 0))
            chosen = avail[0]
            sched[d] = chosen
            load[chosen] = load.get(chosen, 0) + 1

    # Build final dict keyed by date string, include program NC days
    result = {}
    d = first
    while d <= last:
        dk = d.isoformat()
        if d.weekday() >= 5:
            d += timedelta(1); continue
        if is_program_nc(d, cfg):
            result[dk] = {"type": "no_call"}
        else:
            att = sched.get(d)
            result[dk] = {"type": "weekday", "attending": att or "UNCOVERED"}
            if not att:
                warnings.append(f"{dk}: No attending assigned — UNCOVERED")
        d += timedelta(1)

    return result, warnings


# ─────────────────────────────────────────────────────────────
# EXCEL EXPORT
# ─────────────────────────────────────────────────────────────
def export_xlsx(all_scheds, cfg):
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    import copy

    wb = Workbook()
    wb.remove(wb.active)

    def fill(h): return PatternFill("solid", fgColor=h)
    def font(bold=False, sz=10, color="111827"):
        return Font(name="Arial", bold=bold, size=sz, color=color)
    thin = Side(style="thin", color="D1D5DB")
    def bord(): return Border(left=thin,right=thin,top=thin,bottom=thin)
    def align(h="center",v="center",wrap=False):
        return Alignment(horizontal=h,vertical=v,wrap_text=wrap)

    COLORS = [
        "DBEAFE","D1FAE5","EDE9FE","FEF3C7","FCE7F3","FFEDD5",
        "E0F2FE","F0FDF4","F5F3FF","FFFBEB","FDF2F8","ECFDF5",
        "EFF6FF","FEF9C3",
    ]
    att_color = {}
    pool = [a["name"] for a in active_attendings(cfg)]
    for i, name in enumerate(sorted(pool)):
        att_color[name] = COLORS[i % len(COLORS)]

    combined = {a["name"]: 0 for a in cfg["attendings"]}

    for (year, month), sched in sorted(all_scheds.items()):
        mlabel = date(year, month, 1).strftime("%b %Y")
        ws = wb.create_sheet(mlabel)
        ws.merge_cells("A1:G1")
        ws["A1"].value = date(year,month,1).strftime("%B %Y").upper() + \
                         "  —  BAYSTATE PSYCHIATRY ATTENDING CALL"
        ws["A1"].font  = font(bold=True,sz=13,color="FFFFFF")
        ws["A1"].fill  = fill("1B4F3C")
        ws["A1"].alignment = align()
        ws.row_dimensions[1].height = 26

        for col, day in enumerate(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],1):
            c = ws.cell(2, col, day)
            c.font = font(bold=True,sz=11,color="FFFFFF")
            c.fill = fill("1B4F3C")
            c.alignment = align(); c.border = bord()
            ws.column_dimensions[get_column_letter(col)].width = 20
        ws.row_dimensions[2].height = 20

        first_dow = date(year,month,1).weekday()
        num_days  = calendar.monthrange(year,month)[1]
        current_row = 3; ROW_H = 32
        total_weeks = ((num_days + first_dow - 1) // 7) + 1

        for wi in range(total_weeks):
            ws.row_dimensions[current_row + wi].height = ROW_H

        for day_num in range(1, num_days+1):
            d   = date(year, month, day_num)
            dow = d.weekday(); col = dow + 1
            slot = day_num - 1 + first_dow; week_i = slot // 7
            row  = current_row + week_i
            dk   = d.isoformat()
            e    = sched.get(dk, {})

            cell = ws.cell(row, col)
            cell.border = bord(); cell.alignment = align(h="left", v="center", wrap=True)

            if dow >= 5:
                cell.fill = fill("F3F4F6")
                cell.value = str(day_num)
                cell.font = font(sz=10, color="9CA3AF")
            elif e.get("type") == "no_call":
                cell.fill = fill("FEF9C3")
                cell.value = f"{day_num}  — No call"
                cell.font = font(sz=10, color="92400E", italic=True)
            else:
                att = e.get("attending","")
                bg  = att_color.get(att,"FFFFFF") if att != "UNCOVERED" else "FCA5A5"
                cell.fill = fill(bg)
                last = att.split()[-1] if att and att != "UNCOVERED" else att
                cell.value = f"  {day_num}  {last}"
                cell.font  = font(bold=True,sz=10,
                                  color="7F1D1D" if att=="UNCOVERED" else "1C1A16")
                if att and att != "UNCOVERED":
                    combined[att] = combined.get(att, 0) + 1

        # Empty weekend cells
        for wi in range(total_weeks):
            row = current_row + wi
            for col in [6,7]:
                cell = ws.cell(row,col)
                if cell.value is None:
                    cell.fill=fill("F8FAFC"); cell.border=bord()

    # Summary sheet
    ws_s = wb.create_sheet("Summary")
    wb.move_sheet("Summary", offset=-(len(wb.sheetnames)-1))
    ws_s.column_dimensions["A"].width = 28
    ws_s.column_dimensions["B"].width = 14
    ws_s.column_dimensions["C"].width = 14

    for col, hdr in enumerate(["Attending","Total Calls","Color"],1):
        c = ws_s.cell(1,col,hdr)
        c.fill=fill("1B4F3C"); c.font=font(bold=True,sz=11,color="FFFFFF")
        c.alignment=align(); c.border=bord()

    for i, a in enumerate(sorted(cfg["attendings"], key=lambda x: x["name"]),2):
        bg = att_color.get(a["name"],"FFFFFF")
        for col,val in enumerate([a["name"], combined.get(a["name"],0), ""],1):
            c=ws_s.cell(i,col,val)
            c.fill=fill(bg if col==3 else "FFFFFF")
            c.font=font(sz=10); c.alignment=align(h="left" if col==1 else "center")
            c.border=bord()
        ws_s.cell(i,3).fill=fill(bg)

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# CSS  (matches resident scheduler aesthetic)
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #1C1C1E; }
[data-testid="stSidebar"] * { color: #F2F2F7 !important; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] { background:#2C2C2E; border-radius:6px; padding:6px 16px; color:#8E8E93; }
.stTabs [aria-selected="true"] { background:#1B4F3C !important; color:white !important; }
.cal-header-row { display:grid; grid-template-columns:repeat(7,1fr); gap:3px; margin-top:12px; }
.cal-grid       { display:grid; grid-template-columns:repeat(7,1fr); gap:3px; margin-top:3px; }
.dow-hdr { text-align:center; font-size:11px; font-weight:600; color:#8E8E93; padding:6px 2px; }
.cal-cell { background:#2C2C2E; border-radius:6px; padding:6px 8px; min-height:72px; font-size:12px; }
.cal-cell.weekend  { background:#242424; }
.cal-cell.no-call  { background:#2A2A1A; }
.cal-cell.assigned { border-left:3px solid #1B4F3C; }
.cal-cell.uncov    { background:#3B1515; border-left:3px solid #EF4444; }
.cal-cell.empty    { background:transparent; min-height:0; }
.day-num { font-weight:700; color:#6B6760; font-size:11px; margin-bottom:4px; }
.att-name { font-size:12px; font-weight:600; color:#F2F2F7; }
.warn-hard { background:#3B1515; border-left:3px solid #EF4444; padding:6px 10px; border-radius:4px; font-family:monospace; font-size:12px; margin-bottom:4px; color:#FCA5A5; }
.warn-info { background:#1A2A1A; border-left:3px solid #10B981; padding:6px 10px; border-radius:4px; font-size:12px; margin-bottom:4px; color:#6EE7B7; }
.count-row { display:flex; align-items:center; gap:10px; padding:6px 12px; border-radius:6px; background:#2C2C2E; margin-bottom:4px; }
.count-bar-bg { flex:1; height:6px; background:#3A3A3C; border-radius:3px; overflow:hidden; max-width:120px; }
.count-bar { height:6px; border-radius:3px; background:#1B4F3C; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏥 Attending Call")
    st.markdown("---")

    with st.expander("💾 Config", expanded=False):
        cfg_bytes = json.dumps(get_cfg(), indent=2).encode()
        st.download_button("⬇ Download config", cfg_bytes,
                           file_name="attending_config.json",
                           mime="application/json", use_container_width=True)
        up = st.file_uploader("⬆ Upload config", type="json", label_visibility="collapsed")
        if up:
            try:
                save_cfg(json.load(up)); st.success("Loaded!"); st.rerun()
            except Exception as e:
                st.error(f"Invalid JSON: {e}")

    st.markdown("---")
    st.markdown("**Generate schedule**")

    MONTH_MAP = {"July":7,"August":8,"September":9,"October":10,
                 "November":11,"December":12,"January":1,"February":2,
                 "March":3,"April":4,"May":5,"June":6}
    sel_month = st.selectbox("Starting month", list(MONTH_MAP.keys()), index=0)
    sel_year  = st.selectbox("Year", [2026,2027], index=0)
    sel_n     = st.selectbox("# of months", [1,2,3,4,5,6,12], index=0)
    use_seed  = st.checkbox("Fix random seed (reproducible)", value=False)
    seed_val  = st.number_input("Seed", value=42, step=1) if use_seed else None

    if st.button("▶  Generate Schedule", type="primary", use_container_width=True):
        cfg = get_cfg()
        if not active_attendings(cfg):
            st.error("No active attendings.")
        else:
            with st.spinner("Generating…"):
                all_scheds = {}; all_warns = {}
                y, m = sel_year, MONTH_MAP[sel_month]
                for _ in range(sel_n):
                    sched, warns = schedule_month(y, m, cfg, seed=seed_val)
                    all_scheds[(y,m)] = sched; all_warns[(y,m)] = warns
                    m += 1
                    if m > 12: m=1; y+=1
                st.session_state.att_scheds = all_scheds
                st.session_state.att_warns  = all_warns
                total = sum(len(v) for v in all_warns.values())
                st.success(f"Done!{' ' + str(total) + ' warning(s).' if total else ''}")

    if "att_scheds" in st.session_state and st.session_state.att_scheds:
        cfg = get_cfg()
        xlsx = export_xlsx(st.session_state.att_scheds, cfg)
        months_list = sorted(st.session_state.att_scheds.keys())
        label = date(months_list[0][0],months_list[0][1],1).strftime("%b%Y")
        if len(months_list)>1:
            label+=f"_to_{date(months_list[-1][0],months_list[-1][1],1).strftime('%b%Y')}"
        st.download_button("⬇ Download Excel", xlsx,
                           file_name=f"Attending_Call_{label}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

    if "att_scheds" in st.session_state:
        if st.button("🗑 Clear", use_container_width=True):
            del st.session_state["att_scheds"], st.session_state["att_warns"]
            st.rerun()

# ─────────────────────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────────────────────
tab_cal, tab_att, tab_nc, tab_pnc = st.tabs([
    "📅 Schedule", "👥 Attendings", "🚫 No-Call Requests", "📵 Program No-Call"
])

# ── Tab 1: Schedule ──────────────────────────────────────────
with tab_cal:
    if "att_scheds" not in st.session_state or not st.session_state.att_scheds:
        st.info("No schedule yet — use the sidebar to generate one.")
    else:
        cfg = get_cfg()
        months = sorted(st.session_state.att_scheds.keys())
        labels = [date(y,m,1).strftime("%B %Y") for y,m in months]
        sel_i  = st.selectbox("Month", range(len(months)), format_func=lambda i: labels[i])
        year, month = months[sel_i]
        sched = st.session_state.att_scheds[(year,month)]

        st.markdown(f"### {labels[sel_i]}")

        # Build color map for this render
        pool = sorted({e["attending"] for e in sched.values()
                       if e.get("type")=="weekday" and e.get("attending","")!="UNCOVERED"})
        PALETTE = [
            "#3B82F6","#10B981","#8B5CF6","#F59E0B","#EC4899","#EF4444",
            "#06B6D4","#84CC16","#F97316","#6366F1","#14B8A6","#A855F7",
            "#22C55E","#0EA5E9",
        ]
        name_color = {name: PALETTE[i % len(PALETTE)] for i,name in enumerate(pool)}

        # Count this month
        counts = {}
        for e in sched.values():
            if e.get("type")=="weekday" and e.get("attending") not in ("","UNCOVERED"):
                counts[e["attending"]] = counts.get(e["attending"],0) + 1

        # Legend
        st.markdown("**Color key**")
        cols = st.columns(min(7, len(name_color)))
        for i, (name, color) in enumerate(name_color.items()):
            cols[i % len(cols)].markdown(
                f'<span style="display:inline-block;background:{color};color:white;'
                f'padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500">'
                f'{name.split()[-1]}</span>', unsafe_allow_html=True)

        # Calendar
        first_dow = date(year,month,1).weekday()
        num_days  = calendar.monthrange(year,month)[1]

        html = '<div class="cal-header-row">'
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            html += f'<div class="dow-hdr">{d}</div>'
        html += '</div><div class="cal-grid">'

        for slot in range(42):
            day_num = slot - first_dow + 1
            if day_num < 1 or day_num > num_days:
                html += '<div class="cal-cell empty"></div>'; continue

            d = date(year,month,day_num); dk = d.isoformat(); dow = d.weekday()

            if dow >= 5:
                html += f'<div class="cal-cell weekend"><div class="day-num">{day_num}</div></div>'
                continue

            e = sched.get(dk, {})
            if e.get("type") == "no_call":
                html += f'<div class="cal-cell no-call"><div class="day-num">{day_num}</div>'
                html += '<div style="font-size:10px;color:#8E8E93;font-style:italic">no call</div></div>'
                continue

            att = e.get("attending","")
            dow_name = ["Mon","Tue","Wed","Thu","Fri"][dow]
            if att == "UNCOVERED":
                html += f'<div class="cal-cell uncov"><div class="day-num">{day_num} {dow_name}</div>'
                html += '<div class="att-name" style="color:#FCA5A5">UNCOVERED</div></div>'
            elif att:
                color = name_color.get(att,"#1B4F3C")
                last  = att.split()[-1]
                html += f'<div class="cal-cell assigned" style="border-left-color:{color}">'
                html += f'<div class="day-num">{day_num} <span style="font-weight:400;font-size:9px">{dow_name}</span></div>'
                html += f'<div class="att-name" style="color:{color}">{last}</div></div>'
            else:
                html += f'<div class="cal-cell"><div class="day-num">{day_num} {dow_name}</div></div>'

        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

        # Call counts this month
        if counts:
            st.markdown("---")
            st.markdown("**Call counts this month**")
            max_count = max(counts.values(), default=1)
            count_cols = st.columns(min(4, len(counts)))
            for i, (name, cnt) in enumerate(sorted(counts.items(), key=lambda x: -x[1])):
                col = count_cols[i % len(count_cols)]
                color = name_color.get(name,"#1B4F3C")
                pct = int(cnt/max_count*100)
                col.markdown(
                    f'<div class="count-row">'
                    f'<span style="font-size:12px;font-weight:500;min-width:110px">{name.split()[-1]}</span>'
                    f'<div class="count-bar-bg"><div class="count-bar" style="width:{pct}%;background:{color}"></div></div>'
                    f'<span style="font-family:monospace;font-size:12px;font-weight:600">{cnt}</span>'
                    f'</div>', unsafe_allow_html=True)

        # Warnings
        warns = st.session_state.att_warns.get((year,month),[])
        if warns:
            st.markdown("---")
            for w in warns:
                cls = "warn-hard" if "UNCOVERED" in w else "warn-info"
                st.markdown(f'<div class="{cls}">{w}</div>', unsafe_allow_html=True)


# ── Tab 2: Attendings ────────────────────────────────────────
with tab_att:
    cfg = get_cfg()
    st.markdown("### Attending Roster")

    c1, c2 = st.columns([2,5])
    if c1.button("➕ Add Attending"):
        st.session_state.att_action = "add"
        st.session_state.att_edit_name = None

    # Table
    for a in sorted(cfg["attendings"], key=lambda x: x["name"]):
        active = a.get("active", True)
        c1,c2,c3 = st.columns([4,1,1])
        c1.markdown(f'<span style="opacity:{"1.0" if active else "0.4"};font-weight:500">{a["name"]}</span>',
                    unsafe_allow_html=True)
        c2.write("✅" if active else "⏸")
        if c3.button("✎", key=f"eatt_{a['name']}"):
            st.session_state.att_action = "edit"
            st.session_state.att_edit_name = a["name"]

    # Add/Edit form
    action = st.session_state.get("att_action")
    if action in ("add","edit"):
        edit_name = st.session_state.get("att_edit_name")
        existing  = next((a for a in cfg["attendings"] if a["name"]==edit_name), None)
        st.markdown("---")
        st.markdown(f"#### {'Add' if action=='add' else 'Edit'} Attending")
        with st.form("att_form"):
            name_in   = st.text_input("Full Name", value="" if not existing else existing["name"])
            active_in = st.checkbox("Active", value=True if not existing else existing.get("active",True))
            c1,c2 = st.columns(2)
            saved     = c1.form_submit_button("Save", type="primary")
            cancelled = c2.form_submit_button("Cancel")
            remove    = st.form_submit_button("🗑 Remove / Deactivate") if existing else False

        if cancelled:
            del st.session_state["att_action"]; st.rerun()
        if saved:
            if not name_in.strip(): st.error("Enter a name.")
            else:
                cfg2 = get_cfg()
                if action == "add":
                    cfg2["attendings"].append({"name":name_in.strip(),"active":True,"no_call":[]})
                else:
                    for a in cfg2["attendings"]:
                        if a["name"] == edit_name:
                            a["name"]=name_in.strip(); a["active"]=active_in
                save_cfg(cfg2); del st.session_state["att_action"]; st.rerun()
        if remove and existing:
            cfg2 = get_cfg()
            ans = "deactivate"  # always deactivate (keeps no-call history)
            for a in cfg2["attendings"]:
                if a["name"] == edit_name: a["active"] = False
            save_cfg(cfg2); del st.session_state["att_action"]; st.rerun()


# ── Tab 3: No-Call Requests ──────────────────────────────────
with tab_nc:
    cfg = get_cfg()
    st.markdown("### No-Call Requests")

    pool = [a["name"] for a in active_attendings(cfg)]
    if not pool:
        st.info("No active attendings.")
    else:
        sel_att = st.selectbox("Attending", sorted(pool))

        if "att_nc_ym" not in st.session_state:
            st.session_state.att_nc_ym = (2026,7)
        ny,nm = st.session_state.att_nc_ym
        c1,c2,c3 = st.columns([1,3,1])
        if c1.button("◀", key="anc_prev"):
            nm-=1
            if nm<1: nm=12; ny-=1
            st.session_state.att_nc_ym=(ny,nm); st.rerun()
        c2.markdown(f"<h4 style='text-align:center'>{date(ny,nm,1).strftime('%B %Y')}</h4>",
                    unsafe_allow_html=True)
        if c3.button("▶", key="anc_next"):
            nm+=1
            if nm>12: nm=1; ny+=1
            st.session_state.att_nc_ym=(ny,nm); st.rerun()

        att_data = next((a for a in cfg["attendings"] if a["name"]==sel_att), {})
        nc_dates = set(att_data.get("no_call",[]))

        first_dow=date(ny,nm,1).weekday(); num_days=calendar.monthrange(ny,nm)[1]
        html='<div class="cal-header-row">'
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            html+=f'<div class="dow-hdr">{d}</div>'
        html+='</div><div class="cal-grid">'
        for slot in range(42):
            day_num=slot-first_dow+1
            if day_num<1 or day_num>num_days:
                html+='<div class="cal-cell empty"></div>'; continue
            d=date(ny,nm,day_num); dk=d.isoformat(); dow=d.weekday()
            if dow>=5:
                html+=f'<div class="cal-cell weekend"><div class="day-num">{day_num}</div></div>'
                continue
            is_nc=dk in nc_dates
            cls="cal-cell no-call" if is_nc else "cal-cell"
            html+=f'<div class="{cls}"><div class="day-num">{day_num}</div>'
            if is_nc: html+='<div style="font-size:10px;color:#93C5FD">🚫 no call</div>'
            html+='</div>'
        html+='</div>'
        st.markdown(html, unsafe_allow_html=True)

        st.markdown("---")
        with st.form("anc_form"):
            nc_date_in = st.date_input("Date", value=date(ny,nm,1))
            c1,c2 = st.columns(2)
            add_nc = c1.form_submit_button("🚫 Mark no-call", type="primary")
            rem_nc = c2.form_submit_button("✅ Remove no-call")

        if add_nc:
            cfg2=get_cfg(); dk2=nc_date_in.isoformat()
            for a in cfg2["attendings"]:
                if a["name"]==sel_att:
                    if dk2 not in a.get("no_call",[]): a.setdefault("no_call",[]).append(dk2)
            save_cfg(cfg2); st.rerun()
        if rem_nc:
            cfg2=get_cfg(); dk2=nc_date_in.isoformat()
            for a in cfg2["attendings"]:
                if a["name"]==sel_att:
                    a["no_call"]=[d for d in a.get("no_call",[]) if d!=dk2]
            save_cfg(cfg2); st.rerun()

        all_nc = sorted(att_data.get("no_call",[]))
        if all_nc:
            with st.expander(f"All no-call dates for {sel_att} ({len(all_nc)})"):
                for dk in all_nc:
                    st.write(f"• {date.fromisoformat(dk).strftime('%A, %B %-d, %Y')}")


# ── Tab 4: Program No-Call Days ──────────────────────────────
with tab_pnc:
    cfg = get_cfg()
    st.markdown("### Program-Wide No-Call Days")
    st.caption("No attending is assigned on these dates.")

    pnc = sorted(cfg.get("program_no_call",[]))
    if pnc:
        for dk in pnc:
            c1,c2=st.columns([4,1])
            c1.write(f"📵  {date.fromisoformat(dk).strftime('%A, %B %-d, %Y')}")
            if c2.button("Remove", key=f"dpnc_{dk}"):
                cfg2=get_cfg()
                cfg2["program_no_call"]=[d for d in cfg2["program_no_call"] if d!=dk]
                save_cfg(cfg2); st.rerun()
    else:
        st.info("No program no-call days configured.")

    st.markdown("---")
    with st.form("pnc_att_form"):
        pnc_in = st.date_input("Add date", value=date(2026,9,26))
        if st.form_submit_button("➕ Add", type="primary"):
            cfg2=get_cfg(); dk2=pnc_in.isoformat()
            if dk2 not in cfg2.get("program_no_call",[]):
                cfg2.setdefault("program_no_call",[]).append(dk2)
                cfg2["program_no_call"].sort()
            save_cfg(cfg2); st.rerun()
