import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Fullscreen
from streamlit_folium import st_folium
import plotly.express as px
import os

st.set_page_config(
    page_title="Lebanon Events Mobile",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.block-container {
    padding-top: 2.1rem;
    padding-left: 0.45rem;
    padding-right: 0.45rem;
    padding-bottom: 0.5rem;
}

h1 {
    font-size: 1.05rem !important;
    line-height: 1.25 !important;
    margin-top: 0.6rem !important;
    margin-bottom: 0.3rem !important;
    white-space: normal !important;
}

h2, h3 {
    font-size: 0.95rem !important;
}

iframe {
    width: 100% !important;
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    margin-top: 6px;
    margin-bottom: 8px;
}

.kpi-card {
    background: #f7f7f9;
    border: 1px solid #e5e5e5;
    border-radius: 10px;
    padding: 7px 5px;
    text-align: center;
}

.kpi-card span {
    display: block;
    font-size: 0.68rem;
    color: #666;
}

.kpi-card b {
    display: block;
    font-size: 1rem;
    color: #111;
}

.small-note {
    font-size: 0.72rem;
    color: #666;
    margin-bottom: 4px;
}

div[data-testid="stRadio"] label {
    font-size: 0.75rem !important;
}

</style>
""", unsafe_allow_html=True)

DATA_FILE = "events.csv"

@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        st.error("events.csv not found.")
        st.stop()

    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")

    for col in [
        "latitude",
        "longitude",
        "location_killed",
        "location_injured",
        "location_children"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

df = load_data()
filtered = df.copy()

st.title("Lebanon Events")
st.caption("May 2026 · Mobile summary view")

# =====================
# Filters
# =====================

with st.expander("Filters", expanded=False):

    tab_place, tab_type = st.tabs(["Place", "Date / Type"])

    with tab_place:
        for col, label in [
            ("district", "District"),
            ("village_location", "Village")
        ]:
            if col in filtered.columns:
                vals = sorted(filtered[col].dropna().astype(str).unique())
                selected = st.multiselect(label, vals)
                if selected:
                    filtered = filtered[filtered[col].astype(str).isin(selected)]

    with tab_type:
        if not filtered["event_date"].dropna().empty:
            min_date = filtered["event_date"].min().date()
            max_date = filtered["event_date"].max().date()

            date_range = st.date_input(
                "Date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )

            if isinstance(date_range, tuple) and len(date_range) == 2:
                filtered = filtered[
                    (filtered["event_date"].dt.date >= date_range[0]) &
                    (filtered["event_date"].dt.date <= date_range[1])
                ]

        if "attack_type" in filtered.columns:
            vals = sorted(filtered["attack_type"].dropna().astype(str).unique())
            selected = st.multiselect("Attack type", vals)
            if selected:
                filtered = filtered[filtered["attack_type"].astype(str).isin(selected)]

# =====================
# Data summaries
# =====================

casualty_df = filtered[
    filtered["count_for_casualty_totals"].astype(str).str.lower().eq("yes")
].copy()

unique_events = filtered.drop_duplicates("event_id")

total_events = unique_events["event_id"].nunique()
total_killed = int(casualty_df["location_killed"].fillna(0).sum())
total_injured = int(casualty_df["location_injured"].fillna(0).sum())
total_children = int(casualty_df["location_children"].fillna(0).sum())
affected_villages = filtered["village_location"].dropna().nunique()
records_count = len(filtered)

st.markdown(f"""
<div class="kpi-grid">
  <div class="kpi-card"><span>Events</span><b>{total_events}</b></div>
  <div class="kpi-card"><span>Killed</span><b>{total_killed}</b></div>
  <div class="kpi-card"><span>Injured</span><b>{total_injured}</b></div>
  <div class="kpi-card"><span>Children</span><b>{total_children}</b></div>
  <div class="kpi-card"><span>Villages</span><b>{affected_villages}</b></div>
  <div class="kpi-card"><span>Records</span><b>{records_count}</b></div>
</div>
""", unsafe_allow_html=True)

section = st.radio(
    "View",
    ["Map", "Timeline", "Villages", "Events"],
    horizontal=True
)

# =====================
# Map
# =====================

def show_map():
    map_df = filtered.dropna(subset=["latitude", "longitude"]).copy()

    map_df = map_df[
        (map_df["latitude"] >= 33.0) &
        (map_df["latitude"] <= 34.8) &
        (map_df["longitude"] >= 35.0) &
        (map_df["longitude"] <= 36.8)
    ]

    m = folium.Map(
        location=[33.85, 35.85],
        zoom_start=8,
        tiles="CartoDB positron",
        control_scale=True
    )

    m.fit_bounds([[33.0, 35.0], [34.8, 36.8]])
    Fullscreen(position="topright").add_to(m)

    cluster = MarkerCluster().add_to(m)

    for _, row in map_df.iterrows():
        popup = f"""
        <div style="width:260px;">
        <b>Village:</b> {row.get("village_location", "")}<br>
        <b>District:</b> {row.get("district", "")}<br>
        <b>Date:</b> {row.get("event_date", "")}<br>
        <b>Type:</b> {row.get("attack_type", "")}<br>
        <b>Killed:</b> {row.get("location_killed", "")}<br>
        <b>Injured:</b> {row.get("location_injured", "")}<br>
        <b>Children:</b> {row.get("location_children", "")}<br>
        </div>
        """

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6,
            popup=folium.Popup(popup, max_width=280),
            fill=True
        ).add_to(cluster)

    st_folium(m, use_container_width=True, height=420)

# =====================
# Timeline
# =====================

def show_timeline():
    if casualty_df.empty:
        st.info("No casualty records after filtering.")
        return

    daily = (
        casualty_df
        .dropna(subset=["event_date"])
        .assign(day=lambda x: x["event_date"].dt.date)
        .groupby("day")
        .agg(
            events=("event_id", "nunique"),
            killed=("location_killed", "sum"),
            injured=("location_injured", "sum"),
            children=("location_children", "sum")
        )
        .reset_index()
    )

    fig = px.line(
        daily,
        x="day",
        y=["killed", "injured", "children"],
        markers=True
    )

    fig.update_layout(
        height=320,
        margin=dict(l=5, r=5, t=15, b=5),
        legend=dict(orientation="h", y=-0.25),
        xaxis_title="",
        yaxis_title=""
    )

    st.plotly_chart(fig, use_container_width=True)

# =====================
# Villages
# =====================

def show_villages():
    if casualty_df.empty:
        st.info("No records after filtering.")
        return

    top = (
        casualty_df
        .groupby("village_location")
        .agg(events=("event_id", "nunique"))
        .reset_index()
        .sort_values("events", ascending=False)
        .head(10)
    )

    fig = px.bar(
        top,
        x="events",
        y="village_location",
        orientation="h"
    )

    fig.update_layout(
        height=340,
        margin=dict(l=5, r=5, t=15, b=5),
        xaxis_title="",
        yaxis_title=""
    )

    st.plotly_chart(fig, use_container_width=True)

# =====================
# Events
# =====================

def show_events():
    search = st.text_input("Search")

    table = filtered.copy()

    if search:
        table = table[
            table["event_summary_focus"]
            .fillna("")
            .str.contains(search, case=False, na=False)
        ]

    cols = [
        "event_date",
        "village_location",
        "district",
        "attack_type",
        "location_killed",
        "location_injured",
        "location_children",
        "event_summary_focus"
    ]

    cols = [c for c in cols if c in table.columns]

    table = table[cols].rename(columns={
        "event_date": "Date",
        "village_location": "Village",
        "district": "District",
        "attack_type": "Type",
        "location_killed": "Killed",
        "location_injured": "Injured",
        "location_children": "Children",
        "event_summary_focus": "Summary"
    })

    st.dataframe(table, use_container_width=True, height=410)

# =====================
# Render
# =====================

if section == "Map":
    show_map()

elif section == "Timeline":
    show_timeline()

elif section == "Villages":
    show_villages()

elif section == "Events":
    show_events()