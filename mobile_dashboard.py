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
    padding-top: 0.6rem;
    padding-left: 0.35rem;
    padding-right: 0.35rem;
}
h1 {font-size: 1.1rem !important;}
h2, h3 {font-size: 0.95rem !important;}
[data-testid="stMetricValue"] {font-size: 1rem !important;}
[data-testid="stMetricLabel"] {font-size: 0.7rem !important;}
iframe {width: 100% !important;}
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

    for col in ["latitude", "longitude", "location_killed", "location_injured", "location_children"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

df = load_data()
filtered = df.copy()

st.title("Lebanon Events — May 2026")

with st.expander("Filters"):
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

    for col, label in [
        ("district", "District"),
        ("village_location", "Village"),
        ("attack_type", "Attack type")
    ]:
        if col in filtered.columns:
            vals = sorted(filtered[col].dropna().astype(str).unique())
            selected = st.multiselect(label, vals)
            if selected:
                filtered = filtered[filtered[col].astype(str).isin(selected)]

casualty_df = filtered[
    filtered["count_for_casualty_totals"].astype(str).str.lower().eq("yes")
].copy()

unique_events = filtered.drop_duplicates("event_id")

total_events = unique_events["event_id"].nunique()
total_killed = int(casualty_df["location_killed"].fillna(0).sum())
total_injured = int(casualty_df["location_injured"].fillna(0).sum())
total_children = int(casualty_df["location_children"].fillna(0).sum())
affected_villages = filtered["village_location"].dropna().nunique()

c1, c2 = st.columns(2)
c1.metric("Events", total_events)
c2.metric("Killed", total_killed)

c3, c4 = st.columns(2)
c3.metric("Injured", total_injured)
c4.metric("Children", total_children)

c5, c6 = st.columns(2)
c5.metric("Villages", affected_villages)
c6.metric("Records", len(filtered))

section = st.radio(
    "View",
    ["Map", "Timeline", "Top villages", "Events"],
    horizontal=True
)

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
        <b>Village:</b> {row.get("village_location", "")}<br>
        <b>District:</b> {row.get("district", "")}<br>
        <b>Date:</b> {row.get("event_date", "")}<br>
        <b>Killed:</b> {row.get("location_killed", "")}<br>
        <b>Injured:</b> {row.get("location_injured", "")}<br>
        <b>Children:</b> {row.get("location_children", "")}<br>
        """

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6,
            popup=folium.Popup(popup, max_width=280),
            fill=True
        ).add_to(cluster)

    st_folium(m, use_container_width=True, height=420)

def show_timeline():
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
    fig.update_layout(height=330, margin=dict(l=5, r=5, t=15, b=5))
    st.plotly_chart(fig, use_container_width=True)

def show_top_villages():
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
    fig.update_layout(height=350, margin=dict(l=5, r=5, t=15, b=5))
    st.plotly_chart(fig, use_container_width=True)

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

    st.dataframe(table, use_container_width=True, height=420)

if section == "Map":
    show_map()
elif section == "Timeline":
    show_timeline()
elif section == "Top villages":
    show_top_villages()
elif section == "Events":
    show_events()