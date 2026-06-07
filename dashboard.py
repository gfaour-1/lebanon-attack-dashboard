import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Fullscreen, HeatMap
from streamlit_folium import st_folium
import plotly.express as px
import os

st.set_page_config(
    page_title="Lebanon Attack Events — May 2026",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.block-container {
    max-width: 100%;
    padding-top: 2rem;
    padding-left: 1.2rem;
    padding-right: 1.2rem;
    padding-bottom: 0.5rem;
}
h1 {
    font-size: 1.35rem !important;
    line-height: 1.25 !important;
    margin-bottom: 0.5rem !important;
}
h2 {font-size: 1.1rem !important;}
h3 {font-size: 1rem !important;}
[data-testid="stMetricValue"] {font-size: 1.25rem;}
iframe {width: 100% !important;}
</style>
""", unsafe_allow_html=True)

DATA_FILE = "events.csv"

@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        st.error(f"File not found: {DATA_FILE}")
        st.stop()

    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")

    for col in [
        "latitude", "longitude",
        "location_killed", "location_injured", "location_children",
        "source_count", "post_count"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

df = load_data()

# =====================
# Sidebar
# =====================

st.sidebar.title("Lebanon Events")

page = st.sidebar.radio(
    "Page",
    ["Overview", "Map", "Statistics", "Timeline", "Events", "Methodology"]
)

filtered = df.copy()

st.sidebar.header("Filters")

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
        filtered = filtered[
            (filtered["event_date"].dt.date >= date_range[0]) &
            (filtered["event_date"].dt.date <= date_range[1])
        ]

for col, label in [
    ("governorate", "Governorate"),
    ("district", "District"),
    ("village_location", "Village"),
    ("attack_type", "Attack type"),
    ("confidence_level", "Confidence")
]:
    if col in filtered.columns:
        vals = sorted(filtered[col].dropna().astype(str).unique())
        selected = st.sidebar.multiselect(label, vals)
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
mapped_records = filtered.dropna(subset=["latitude", "longitude"]).shape[0]

# =====================
# Components
# =====================

def kpis():
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Events", total_events)
    c2.metric("Killed", total_killed)
    c3.metric("Injured", total_injured)
    c4.metric("Children", total_children)
    c5.metric("Villages", affected_villages)
    c6.metric("Mapped", mapped_records)

def daily_table():
    if casualty_df.empty:
        return pd.DataFrame(columns=["day", "events", "killed", "injured", "children"])

    return (
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

def map_component(height=520, heat=False):
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

    if heat and not map_df.empty:
        HeatMap(map_df[["latitude", "longitude"]].values.tolist(), radius=20).add_to(m)

    cluster = MarkerCluster().add_to(m)

    for _, row in map_df.iterrows():
        popup = f"""
        <div style="width:390px;">
        <b>Village:</b> {row.get("village_location", "")}<br>
        <b>District:</b> {row.get("district", "")}<br>
        <b>Governorate:</b> {row.get("governorate", "")}<br>
        <b>Date:</b> {row.get("event_date", "")}<br>
        <b>Type:</b> {row.get("attack_type", "")}<br>
        <b>Killed:</b> {row.get("location_killed", "")}<br>
        <b>Injured:</b> {row.get("location_injured", "")}<br>
        <b>Children:</b> {row.get("location_children", "")}<br>
        <b>Allocation:</b> {row.get("casualty_allocation", "")}<br>
        <hr>
        {row.get("event_summary_focus", "")}
        </div>
        """

        casualties = (
            (0 if pd.isna(row.get("location_killed")) else row.get("location_killed")) +
            (0 if pd.isna(row.get("location_injured")) else row.get("location_injured"))
        )

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=5 + min(casualties * 0.5, 12),
            popup=folium.Popup(popup, max_width=450),
            fill=True
        ).add_to(cluster)

    st_folium(m, use_container_width=True, height=height)

def table_component(height=560):
    cols = [
        "event_id", "event_date", "village_location", "district", "governorate",
        "attack_type", "location_killed", "location_injured", "location_children",
        "casualty_allocation", "count_for_casualty_totals",
        "confidence_level", "event_summary_focus"
    ]

    cols = [c for c in cols if c in filtered.columns]

    table = filtered[cols].copy()

    table = table.rename(columns={
        "event_id": "Event ID",
        "event_date": "Date",
        "village_location": "Village",
        "district": "District",
        "governorate": "Governorate",
        "attack_type": "Attack type",
        "location_killed": "Killed",
        "location_injured": "Injured",
        "location_children": "Children",
        "casualty_allocation": "Casualty allocation",
        "count_for_casualty_totals": "Count in totals",
        "confidence_level": "Confidence",
        "event_summary_focus": "Summary"
    })

    st.dataframe(table, use_container_width=True, height=height)

    csv = table.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "Download filtered dataset",
        csv,
        "filtered_events.csv",
        "text/csv"
    )

# =====================
# Main Pages
# =====================

st.title("Lebanon Attack Events — May 2026")

if page == "Overview":
    kpis()

    left, right = st.columns([1.2, 0.8], gap="small")

    with left:
        st.subheader("Map preview")
        map_component(height=450, heat=False)

    with right:
        st.subheader("Daily casualties")
        daily = daily_table()

        fig = px.line(
            daily,
            x="day",
            y=["killed", "injured", "children"],
            markers=True
        )
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

        by_type = (
            unique_events.groupby("attack_type")
            .agg(events=("event_id", "nunique"))
            .reset_index()
        )

        fig2 = px.pie(by_type, names="attack_type", values="events")
        fig2.update_layout(height=245, margin=dict(l=10, r=10, t=15, b=10))
        st.plotly_chart(fig2, use_container_width=True)

elif page == "Map":
    kpis()
    heat = st.toggle("Heatmap", value=False)
    map_component(height=640, heat=heat)

elif page == "Statistics":
    kpis()

    tab1, tab2, tab3 = st.tabs(["Places", "Casualties", "Types"])

    with tab1:
        c1, c2 = st.columns(2, gap="small")

        by_village = (
            casualty_df.groupby("village_location")
            .agg(events=("event_id", "nunique"))
            .reset_index()
            .sort_values("events", ascending=False)
            .head(15)
        )

        fig = px.bar(
            by_village,
            x="events",
            y="village_location",
            orientation="h",
            title="Top villages"
        )
        fig.update_layout(height=430, margin=dict(l=10, r=10, t=40, b=10))
        c1.plotly_chart(fig, use_container_width=True)

        by_district = (
            casualty_df.groupby("district")
            .agg(events=("event_id", "nunique"))
            .reset_index()
            .sort_values("events", ascending=False)
        )

        fig2 = px.bar(
            by_district,
            x="district",
            y="events",
            title="Events by district"
        )
        fig2.update_layout(height=430, margin=dict(l=10, r=10, t=40, b=10))
        c2.plotly_chart(fig2, use_container_width=True)

    with tab2:
        c1, c2 = st.columns(2, gap="small")

        by_district_cas = (
            casualty_df.groupby("district")
            .agg(
                killed=("location_killed", "sum"),
                injured=("location_injured", "sum"),
                children=("location_children", "sum")
            )
            .reset_index()
        )

        fig = px.bar(
            by_district_cas,
            x="district",
            y=["killed", "injured", "children"],
            title="Casualties by district"
        )
        fig.update_layout(height=430)
        c1.plotly_chart(fig, use_container_width=True)

        by_gov = (
            casualty_df.groupby("governorate")
            .agg(
                killed=("location_killed", "sum"),
                injured=("location_injured", "sum"),
                children=("location_children", "sum")
            )
            .reset_index()
        )

        fig2 = px.bar(
            by_gov,
            x="governorate",
            y=["killed", "injured", "children"],
            title="Casualties by governorate"
        )
        fig2.update_layout(height=430)
        c2.plotly_chart(fig2, use_container_width=True)

    with tab3:
        by_type = (
            unique_events.groupby("attack_type")
            .agg(events=("event_id", "nunique"))
            .reset_index()
            .sort_values("events", ascending=False)
        )

        fig = px.pie(
            by_type,
            names="attack_type",
            values="events",
            title="Attack type distribution"
        )
        fig.update_layout(height=460)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Timeline":
    kpis()
    daily = daily_table()

    tab1, tab2 = st.tabs(["Events", "Casualties"])

    with tab1:
        fig = px.bar(daily, x="day", y="events", title="Events per day")
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig = px.line(
            daily,
            x="day",
            y=["killed", "injured", "children"],
            markers=True,
            title="Casualties per day"
        )
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Events":
    search = st.text_input("Search in event summaries")

    if search:
        filtered = filtered[
            filtered["event_summary_focus"]
            .fillna("")
            .str.contains(search, case=False, na=False)
        ]

    table_component(height=610)

elif page == "Methodology":
    st.markdown("""
    ### Methodology

    Public Telegram/news records were filtered, cleaned, deduplicated, and geocoded.

    **Key rule:** when one report mentions several villages with one shared casualty figure,
    casualties are kept at event level and are not multiplied across locations.

    ### Disclaimer

    This is an open-source monitoring dashboard based on public reports and automated processing.
    It is not an official casualty record.
    """)