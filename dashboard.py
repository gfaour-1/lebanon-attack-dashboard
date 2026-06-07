import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Fullscreen, HeatMap
from streamlit_folium import st_folium
import plotly.express as px
import os

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="Lebanon Attack Events Dashboard — May 2026",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# RESPONSIVE CSS
# =====================================================

st.markdown("""
<style>
.block-container {
    max-width: 100%;
    padding-top: 0.5rem;
    padding-bottom: 1rem;
    padding-left: 2rem;
    padding-right: 2rem;
}

section.main > div {
    padding-top: 0rem;
}

[data-testid="stDataFrame"] {
    width: 100% !important;
}

.js-plotly-plot {
    width: 100% !important;
}

iframe {
    width: 100% !important;
}

@media (max-width: 768px) {
    .block-container {
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }

    h1 {
        font-size: 1.8rem !important;
    }

    h2 {
        font-size: 1.4rem !important;
    }

    h3 {
        font-size: 1.2rem !important;
    }
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# DATA
# =====================================================

DATA_FILE = "events.csv"

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
        "location_killed",
        "location_injured",
        "location_children",
        "source_count",
        "post_count"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

df = load_data()

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Overview",
        "Interactive map",
        "Statistics",
        "Timeline",
        "Event explorer",
        "Methodology"
    ]
)

page_width = st.sidebar.selectbox(
    "Display mode",
    ["Responsive", "Wide", "Ultra-wide"]
)

if page_width == "Ultra-wide":
    st.markdown("""
    <style>
    .block-container {
        max-width: 98% !important;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

elif page_width == "Wide":
    st.markdown("""
    <style>
    .block-container {
        max-width: 95% !important;
    }
    </style>
    """, unsafe_allow_html=True)

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

# =====================================================
# CORRECT CASUALTY TOTALS
# =====================================================

casualty_df = filtered[
    filtered["count_for_casualty_totals"].astype(str).str.lower().eq("yes")
].copy()

unique_events = filtered.drop_duplicates("event_id")

total_events = unique_events["event_id"].nunique()
mapped_records = filtered.dropna(subset=["latitude", "longitude"]).shape[0]
affected_villages = filtered["village_location"].dropna().nunique()
affected_districts = filtered["district"].dropna().nunique()

total_killed = int(casualty_df["location_killed"].fillna(0).sum())
total_injured = int(casualty_df["location_injured"].fillna(0).sum())
total_children = int(casualty_df["location_children"].fillna(0).sum())

# =====================================================
# FUNCTIONS
# =====================================================

def show_header():
    st.title("Lebanon Attack Events Dashboard — May 2026")
    st.markdown(
        """
        Structured open-source monitoring dashboard based on public media and Telegram reports.  
        Casualty figures are handled carefully at event level to avoid double-counting after location splitting.
        """
    )


def show_kpis():
    c1, c2, c3 = st.columns(3)
    c1.metric("Unique events", total_events)
    c2.metric("Killed", total_killed)
    c3.metric("Injured", total_injured)

    c4, c5, c6 = st.columns(3)
    c4.metric("Children affected", total_children)
    c5.metric("Affected villages", affected_villages)
    c6.metric("Mapped records", mapped_records)


def make_daily_table():
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


def make_map(show_heatmap=False, fullscreen_mode=False):
    map_df = filtered.dropna(subset=["latitude", "longitude"]).copy()

    map_df = map_df[
        (map_df["latitude"] >= 33.0) &
        (map_df["latitude"] <= 34.8) &
        (map_df["longitude"] >= 35.0) &
        (map_df["longitude"] <= 36.8)
    ]

    tiles = {
        "Light map": "CartoDB positron",
        "OpenStreetMap": "OpenStreetMap",
        "Dark map": "CartoDB dark_matter"
    }

    selected_tile = st.selectbox(
        "Basemap",
        list(tiles.keys()),
        index=0
    )

    map_height = 900 if fullscreen_mode else 650

    m = folium.Map(
        location=[33.85, 35.85],
        zoom_start=8,
        tiles=tiles[selected_tile]
    )

    # Lebanon full extent
    m.fit_bounds([[33.0, 35.0], [34.8, 36.8]])

    Fullscreen(position="topright").add_to(m)

    if show_heatmap:
        heat_data = map_df[["latitude", "longitude"]].dropna().values.tolist()
        if heat_data:
            HeatMap(heat_data, radius=20, blur=15).add_to(m)

    cluster = MarkerCluster(name="Attack events").add_to(m)

    for _, row in map_df.iterrows():
        popup = f"""
        <div style="width:390px;">
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

        killed = 0 if pd.isna(row.get("location_killed")) else row.get("location_killed")
        injured = 0 if pd.isna(row.get("location_injured")) else row.get("location_injured")
        casualties = killed + injured

        radius = 5 + min(casualties * 0.5, 12)

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=radius,
            popup=folium.Popup(popup, max_width=470),
            fill=True
        ).add_to(cluster)

    st_folium(
        m,
        use_container_width=True,
        height=map_height
    )


def display_dataset_table(data):
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

    display_cols = [c for c in display_cols if c in data.columns]

    table = data[display_cols].copy()
    table = table.rename(columns=DISPLAY_NAMES)

    st.dataframe(table, use_container_width=True, height=520)

    csv = table.to_csv(index=False, encoding="utf-8-sig")

    st.download_button(
        label="Download filtered dataset as CSV",
        data=csv,
        file_name="filtered_lebanon_attack_events_may_2026.csv",
        mime="text/csv"
    )


# =====================================================
# MAIN DISPLAY
# =====================================================

show_header()

if page == "Overview":
    st.subheader("Key indicators")
    show_kpis()

    st.subheader("Quick overview")

    col1, col2 = st.columns([1, 1], gap="small")

    with col1:
        by_district = (
            casualty_df
            .groupby("district")
            .agg(events=("event_id", "nunique"))
            .reset_index()
            .sort_values("events", ascending=False)
        )

        fig = px.bar(
            by_district,
            x="district",
            y="events",
            title="Events by district"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        by_type = (
            unique_events
            .groupby("attack_type")
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
        st.plotly_chart(fig, use_container_width=True)

    daily = make_daily_table()

    fig = px.line(
        daily,
        x="day",
        y=["killed", "injured", "children"],
        markers=True,
        title="Daily reported killed, injured, and children affected"
    )
    st.plotly_chart(fig, use_container_width=True)


elif page == "Interactive map":
    st.subheader("Interactive event map")
    show_kpis()

    show_heatmap = st.toggle("Show heatmap layer", value=False)
    fullscreen_mode = st.toggle("Large map mode", value=False)

    make_map(
        show_heatmap=show_heatmap,
        fullscreen_mode=fullscreen_mode
    )


elif page == "Statistics":
    st.subheader("Statistical analysis")
    show_kpis()

    col1, col2 = st.columns([1, 1], gap="small")

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

        fig = px.bar(
            by_village.head(20),
            x="events",
            y="village_location",
            orientation="h",
            title="Top 20 villages / localities by number of events"
        )
        st.plotly_chart(fig, use_container_width=True)

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

        fig = px.bar(
            by_district,
            x="district",
            y=["killed", "injured", "children"],
            title="Reported casualties by district"
        )
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns([1, 1], gap="small")

    with col3:
        by_gov = (
            casualty_df
            .groupby("governorate")
            .agg(
                events=("event_id", "nunique"),
                killed=("location_killed", "sum"),
                injured=("location_injured", "sum"),
                children=("location_children", "sum")
            )
            .reset_index()
            .sort_values("events", ascending=False)
        )

        fig = px.bar(
            by_gov,
            x="governorate",
            y=["killed", "injured", "children"],
            title="Reported casualties by governorate"
        )
        st.plotly_chart(fig, use_container_width=True)

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
            fig = px.bar(
                child_df.head(15),
                x="children",
                y="village_location",
                orientation="h",
                title="Villages / localities with reported children affected"
            )
            st.plotly_chart(fig, use_container_width=True)


elif page == "Timeline":
    st.subheader("Timeline analysis")
    show_kpis()

    daily = make_daily_table()

    fig1 = px.bar(
        daily,
        x="day",
        y="events",
        title="Number of unique events per day"
    )
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.line(
        daily,
        x="day",
        y=["killed", "injured", "children"],
        markers=True,
        title="Daily reported casualties"
    )
    st.plotly_chart(fig2, use_container_width=True)

    fig3 = px.bar(
        daily,
        x="day",
        y=["killed", "injured", "children"],
        title="Daily casualty composition"
    )
    st.plotly_chart(fig3, use_container_width=True)


elif page == "Event explorer":
    st.subheader("Event explorer")

    search_text = st.text_input("Search in event summaries")

    explorer = filtered.copy()

    if search_text:
        explorer = explorer[
            explorer["event_summary_focus"].fillna("").str.contains(
                search_text,
                case=False,
                na=False
            )
        ]

    st.write("Matching records:", len(explorer))
    display_dataset_table(explorer)


elif page == "Methodology":
    st.subheader("Methodology and data notes")

    st.markdown(
        """
        ### Data source
        The dashboard is based on public media and Telegram reports collected for May 2026.

        ### Processing workflow
        1. Public news posts were collected from Telegram channels.
        2. Posts were filtered for attack-related events in Lebanon.
        3. Political statements, cumulative casualty summaries, and non-event records were removed.
        4. Event summaries were analyzed to extract:
           - village / locality
           - district and governorate
           - attack type
           - killed and injured counts
           - children affected when mentioned
        5. Duplicate reports were merged into event-level records.
        6. Locations were geocoded to village/locality centers.
        7. Multi-location events were split for mapping, while casualties were not duplicated.

        ### Casualty allocation rule
        When one report mentions several villages with one shared casualty figure, the casualties are retained at event level and are not multiplied across locations.

        ### Disclaimer
        This dashboard is an open-source monitoring tool based on public reports and automated processing. It is not an official casualty record and should be interpreted with caution.
        """
    )

    st.subheader("Dataset preview")
    display_dataset_table(filtered)