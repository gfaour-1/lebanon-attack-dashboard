import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Fullscreen
from streamlit_folium import st_folium
import plotly.express as px
import os

st.set_page_config(page_title="Lebanon Attack Events Dashboard — May 2026", layout="wide")

DATA_FILE = "lebanon_may_2026_attack_events_corrected_location_casualty_split(1).csv"

DISPLAY_NAMES = {
    "event_id": "Event ID",
    "split_id": "Split ID",
    "event_date": "Event date",
    "village_location": "Village / locality",
    "district": "District",
    "governorate": "Governorate",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "geocode_confidence": "Geocoding confidence",
    "location_extraction_confidence": "Location extraction confidence",
    "casualty_allocation": "Casualty allocation",
    "count_for_casualty_totals": "Count in casualty totals",
    "event_total_killed_from_focus_text": "Event-level killed",
    "event_total_injured_from_focus_text": "Event-level injured",
    "event_total_children_from_focus_text": "Event-level children",
    "location_killed": "Killed at location",
    "location_injured": "Injured at location",
    "location_children": "Children at location",
    "injury_text_note": "Injury note",
    "attack_type": "Attack type",
    "source_count": "Number of sources",
    "post_count": "Number of posts",
    "confidence_level": "Confidence level",
    "warning_flags": "Warnings",
    "event_summary_focus": "Relevant event summary",
    "event_summary_original": "Original event summary",
    "reference_links": "Reference links"
}

@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        st.error(f"File not found: {DATA_FILE}")
        st.stop()

    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")

    numeric_cols = [
        "latitude", "longitude",
        "event_total_killed_from_focus_text",
        "event_total_injured_from_focus_text",
        "event_total_children_from_focus_text",
        "location_killed", "location_injured", "location_children",
        "source_count", "post_count"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

df = load_data()

st.title("Lebanon Attack Events Dashboard — May 2026")

st.markdown(
    """
    This dashboard presents structured media-reported attack events in Lebanon during **May 2026**.
    Casualty figures are handled carefully to avoid double-counting when one event is linked to several locations.
    """
)

# =====================
# Sidebar filters
# =====================

st.sidebar.header("Filters")

filtered = df.copy()

if not filtered["event_date"].dropna().empty:
    min_date = filtered["event_date"].min().date()
    max_date = filtered["event_date"].max().date()

    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["event_date"].dt.date >= start_date) &
            (filtered["event_date"].dt.date <= end_date)
        ]

for col, label in [
    ("governorate", "Governorate"),
    ("district", "District"),
    ("village_location", "Village / locality"),
    ("attack_type", "Attack type"),
    ("confidence_level", "Confidence level"),
    ("geocode_confidence", "Geocoding confidence")
]:
    if col in filtered.columns:
        values = sorted(filtered[col].dropna().astype(str).unique())
        selected = st.sidebar.multiselect(label, values)
        if selected:
            filtered = filtered[filtered[col].astype(str).isin(selected)]

# =====================
# Correct casualty totals
# =====================

# Only count rows explicitly marked Yes to avoid multiplying victims/injuries after location splitting.
casualty_df = filtered[
    filtered["count_for_casualty_totals"].astype(str).str.lower().eq("yes")
].copy()

unique_events = filtered.drop_duplicates("event_id")

total_events = unique_events["event_id"].nunique()
mapped_records = filtered.dropna(subset=["latitude", "longitude"]).shape[0]
affected_villages = filtered["village_location"].dropna().nunique()

total_killed = int(casualty_df["location_killed"].fillna(0).sum())
total_injured = int(casualty_df["location_injured"].fillna(0).sum())
total_children = int(casualty_df["location_children"].fillna(0).sum())

st.subheader("Key indicators")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Unique events", total_events)
c2.metric("Killed", total_killed)
c3.metric("Injured", total_injured)
c4.metric("Children affected", total_children)
c5.metric("Affected villages", affected_villages)
c6.metric("Mapped records", mapped_records)

# =====================
# Map
# =====================

st.subheader("Event map")

map_df = filtered.dropna(subset=["latitude", "longitude"]).copy()

map_df = map_df[
    (map_df["latitude"] >= 33.0) &
    (map_df["latitude"] <= 34.8) &
    (map_df["longitude"] >= 35.0) &
    (map_df["longitude"] <= 36.8)
]

m = folium.Map(location=[33.85, 35.85], zoom_start=8, tiles="CartoDB positron")
m.fit_bounds([[33.0, 35.0], [34.8, 36.8]])
Fullscreen(position="topright").add_to(m)

cluster = MarkerCluster(name="Attack events").add_to(m)

for _, row in map_df.iterrows():
    popup = f"""
    <div style="width:380px;">
    <b>Village / locality:</b> {row.get("village_location", "")}<br>
    <b>District:</b> {row.get("district", "")}<br>
    <b>Governorate:</b> {row.get("governorate", "")}<br>
    <b>Date:</b> {row.get("event_date", "")}<br>
    <b>Attack type:</b> {row.get("attack_type", "")}<br>
    <b>Killed at location:</b> {row.get("location_killed", "")}<br>
    <b>Injured at location:</b> {row.get("location_injured", "")}<br>
    <b>Children at location:</b> {row.get("location_children", "")}<br>
    <b>Casualty allocation:</b> {row.get("casualty_allocation", "")}<br>
    <b>Count in totals:</b> {row.get("count_for_casualty_totals", "")}<br>
    <b>Confidence:</b> {row.get("confidence_level", "")}<br>
    <hr>
    <b>Relevant event summary:</b><br>{row.get("event_summary_focus", "")}
    </div>
    """

    casualties = (
        (0 if pd.isna(row.get("location_killed")) else row.get("location_killed")) +
        (0 if pd.isna(row.get("location_injured")) else row.get("location_injured"))
    )

    radius = 5 + min(casualties * 0.5, 12)

    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=radius,
        popup=folium.Popup(popup, max_width=460),
        fill=True
    ).add_to(cluster)

st_folium(m, width=1300, height=620)

# =====================
# Charts
# =====================

st.subheader("Temporal analysis")

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

fig1 = px.bar(daily, x="day", y="events", title="Number of unique events per day")
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.line(
    daily,
    x="day",
    y=["killed", "injured", "children"],
    markers=True,
    title="Daily reported killed, injured, and children affected"
)
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Spatial analysis")

col1, col2 = st.columns(2)

with col1:
    by_village = (
        casualty_df
        .groupby("village_location")
        .agg(
            events=("event_id", "nunique"),
            killed=("location_killed", "sum"),
            injured=("location_injured", "sum"),
            children=("location_children", "sum")
        )
        .reset_index()
        .sort_values("events", ascending=False)
    )

    fig3 = px.bar(
        by_village.head(20),
        x="events",
        y="village_location",
        orientation="h",
        title="Top 20 villages / localities by number of events"
    )
    st.plotly_chart(fig3, use_container_width=True)

with col2:
    by_district = (
        casualty_df
        .groupby("district")
        .agg(
            events=("event_id", "nunique"),
            killed=("location_killed", "sum"),
            injured=("location_injured", "sum"),
            children=("location_children", "sum")
        )
        .reset_index()
        .sort_values("events", ascending=False)
    )

    fig4 = px.bar(
        by_district,
        x="district",
        y=["killed", "injured", "children"],
        title="Reported casualties by district"
    )
    st.plotly_chart(fig4, use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    by_type = (
        unique_events
        .groupby("attack_type")
        .agg(events=("event_id", "nunique"))
        .reset_index()
        .sort_values("events", ascending=False)
    )

    fig5 = px.pie(
        by_type,
        names="attack_type",
        values="events",
        title="Attack type distribution"
    )
    st.plotly_chart(fig5, use_container_width=True)

with col4:
    child_df = (
        casualty_df
        .groupby("village_location")
        .agg(children=("location_children", "sum"))
        .reset_index()
        .sort_values("children", ascending=False)
    )

    child_df = child_df[child_df["children"] > 0]

    if child_df.empty:
        st.info("No child-related casualty values detected.")
    else:
        fig6 = px.bar(
            child_df.head(15),
            x="children",
            y="village_location",
            orientation="h",
            title="Villages / localities with reported children affected"
        )
        st.plotly_chart(fig6, use_container_width=True)

# =====================
# Dataset table
# =====================

st.subheader("Clean event dataset")

display_cols = [
    "event_id",
    "event_date",
    "village_location",
    "district",
    "governorate",
    "latitude",
    "longitude",
    "attack_type",
    "location_killed",
    "location_injured",
    "location_children",
    "injury_text_note",
    "casualty_allocation",
    "count_for_casualty_totals",
    "source_count",
    "post_count",
    "confidence_level",
    "warning_flags",
    "event_summary_focus",
    "reference_links"
]

display_cols = [c for c in display_cols if c in filtered.columns]

table = filtered[display_cols].copy()
table = table.rename(columns=DISPLAY_NAMES)

st.dataframe(table, use_container_width=True, height=520)

csv = table.to_csv(index=False, encoding="utf-8-sig")

st.download_button(
    label="Download filtered dataset as CSV",
    data=csv,
    file_name="filtered_lebanon_attack_events_may_2026.csv",
    mime="text/csv"
)