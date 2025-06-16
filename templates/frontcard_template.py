import gpxpy
from geopy.distance import geodesic
import folium
import os

def extract_gpx_points(gpx):
    if gpx.tracks:
        return [(p.latitude, p.longitude, p.elevation)
                for track in gpx.tracks
                for segment in track.segments
                for p in segment.points]
    elif gpx.routes:
        return [(p.latitude, p.longitude, p.elevation)
                for rte in gpx.routes
                for p in rte.points]
    else:
        raise ValueError("GPX file does not contain <trk> or <rte> data.")

def process_frontcard(gpx_path, output_dir, critname, year):
    with open(gpx_path, encoding="utf-8") as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    try:
        points = extract_gpx_points(gpx)
    except ValueError as e:
        print(f"⚠️ Skipping {gpx_path}: {e}")
        return

    # Detect laps
    start_point = points[0][:2]
    lap_threshold = 15  # meters
    lap_indices = [0]
    for i, (lat, lon, _) in enumerate(points[1:], start=1):
        if geodesic(start_point, (lat, lon)).meters < lap_threshold:
            if i - lap_indices[-1] > 20:  # avoid duplicates
                lap_indices.append(i)

    if len(lap_indices) < 2:
        print("Not enough laps detected.")
        return

    # Extract full lap
    midpoint = len(lap_indices) // 2
    lap_coords = [
        (lat, lon) for (lat, lon, _) in points[lap_indices[midpoint - 1]:lap_indices[midpoint]]
    ]

    # Close loop if needed
    if geodesic(lap_coords[0], lap_coords[-1]).meters > 3:
        lap_coords.append(lap_coords[0])

    latitudes = [c[0] for c in lap_coords]
    longitudes = [c[1] for c in lap_coords]
    bounds = [[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]]

    # Create fully static map so it is not annoying when scrolling on phone
    m = folium.Map(
        location=[sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes)],
        zoom_start=18,
        tiles="OpenStreetMap",
        zoom_control=False,
        scrollWheelZoom=False,
        dragging=False,
        prefer_canvas=True,
    )
    m.fit_bounds(bounds, max_zoom=17, padding=(50, 50))

    folium.PolyLine(lap_coords, color="darkgreen", weight=6, opacity=0.9).add_to(m)

    # Disable all map interactivity using JS
    m.get_root().html.add_child(folium.Element("""
    <script>
        var map = document.getElementsByClassName('folium-map')[0]._leaflet_map;
        map.touchZoom.disable();
        map.doubleClickZoom.disable();
        map.scrollWheelZoom.disable();
        map.boxZoom.disable();
        map.keyboard.disable();
        map.dragging.disable();
        if (map.tap) map.tap.disable();
    </script>
    """))

    # Render map
    map_html = m.get_root().render()

    # Label if it's ToAD
    is_toad = "toad" in critname.lower()

    frontcard_html = f"""
    <html>
        <head>
            <link rel="stylesheet" type="text/css" href="style.css">
            <style>
                .toad-label {{
                    position: absolute;
                    top: 8px;
                    left: 8px;
                    background-color: #28a745;
                    color: white;
                    font-size: 0.8rem;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-family: sans-serif;
                    z-index: 1000;
                }}
                .map-wrapper {{
                    position: relative;
                }}
            </style>
        </head>
        <body>
            <div class="map-wrapper">
                {"<div class='toad-label'>ToAD</div>" if is_toad else ""}
                {map_html}
            </div>
        </body>
    </html>
    """

    # Save file
    frontcard_filename = f"{critname}_crit_{year}_frontcard.html"
    frontcard_path = os.path.join(output_dir, frontcard_filename)

    os.makedirs(output_dir, exist_ok=True)

    with open(frontcard_path, "w", encoding="utf-8") as f:
        f.write(frontcard_html)

    print(f"✅ Saved frontcard map to {frontcard_path}")
