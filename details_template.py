import gpxpy
import folium
import branca
import json
import os
from geopy.distance import geodesic
from folium.plugins import PolyLineTextPath
from scipy.signal import savgol_filter
import numpy as np
from geopy.geocoders import Nominatim


def process_course(gpx_path, output_dir, critname, year):
    with open(gpx_path, encoding='utf-8') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
        
        # Anonymize GPX metadata and rename track to the crit name
        gpx.name = None
        gpx.description = None
        gpx.author_name = None
        gpx.author_email = None
        gpx.creator = "crit-course-script"
        for track in gpx.tracks:
          print(track.name)
          track.name = f"{critname} Crit {year}"  # ✅ Set clean name
          print(track.name)
          track.description = None
          track.comment = None
          track.source = None
          track.type = None
          track.number = None
            
    with open(os.path.join(output_dir, f"{critname}_crit_{year}.gpx"), "w", encoding="utf-8") as out_gpx:
        out_gpx.write(gpx.to_xml())


    points = [(p.latitude, p.longitude, p.elevation)
              for track in gpx.tracks
              for segment in track.segments
              for p in segment.points]

    if not points:
        print(f":warning: No points found in {gpx_path}")
        return

    # Detect lap start indices
    start_point = points[0][:2]
    lap_threshold = 15  # meters
    lap_indices = [0]
    for i, (lat, lon, _) in enumerate(points[1:], start=1):
        if geodesic(start_point, (lat, lon)).meters < lap_threshold:
            if i - lap_indices[-1] > 50:
                lap_indices.append(i)

    if len(lap_indices) < 3:
        print(":x: Not enough laps to analyze.")
        return

    lap_lengths = [lap_indices[i+1] - lap_indices[i] for i in range(len(lap_indices)-1)]
    median_len = np.median(lap_lengths)
    best_lap = min(range(len(lap_lengths)), key=lambda i: abs(lap_lengths[i] - median_len))

    lap_start = lap_indices[best_lap]
    lap_end = lap_indices[best_lap + 1]

    # lap_end = lap_indices[lap_number + 1]
    lap = points[lap_start:lap_end]
    print(lap_start)
    print(lap_end)

    if geodesic(lap[0][:2], lap[-1][:2]).meters > 5:
    # Force loop closure: append starting point at the end with original elevation
      lap.append((lap[0][0], lap[0][1], lap[0][2]))

    lap_coords = [(p[0], p[1]) for p in lap]
    lap_elevs = [p[2] for p in lap]

    # Smooth elevation for nicer display
    window_length = max(7, len(lap_elevs) // 50)
    if window_length % 2 == 0: window_length += 1
    smoothed = savgol_filter(lap_elevs, window_length, polyorder=2)

    avg_lap = [(lat, lon, ele) for (lat, lon), ele in zip(lap_coords, smoothed)]

    # Map creation
    coords = [(p[0], p[1]) for p in avg_lap]
    elevs = [p[2] for p in avg_lap]
    lat_center = sum(p[0] for p in coords) / len(coords)
    lon_center = sum(p[1] for p in coords) / len(coords)
    
    # Reverse geocode to get the state
    geolocator = Nominatim(user_agent="crit-course-processor")
    location = geolocator.reverse((lat_center, lon_center), language='en')
    state = "Unknown"

    if location and 'state' in location.raw['address']:
      state = location.raw['address']['state']


    m = folium.Map(location=[lat_center, lon_center], zoom_start=17)
    color_scale = branca.colormap.StepColormap(
        colors=["darkgreen", "lightgreen", "yellow", "orange", "red", "darkred"],
        index=[-10, -2, 2, 5, 10, 20],
        vmin=-10, vmax=20, caption="Gradient (%)"
    )

    for i in range(len(coords) - 1):
        elev_diff = elevs[i + 1] - elevs[i]
        horiz_dist = geodesic(coords[i], coords[i + 1]).meters
        gradient = (elev_diff / horiz_dist) * 100 if horiz_dist else 0
        color = "gray" if abs(gradient) < 0.01 else color_scale(gradient)

        segment = folium.PolyLine([coords[i], coords[i + 1]], color=color, weight=8, opacity=0.9,
                                  tooltip=f"Gradient: {gradient:.1f}%").add_to(m)
        
        # Add arrow pointing forward
        PolyLineTextPath(
            segment,
            '➤',
            repeat=True,
            offset=0,
            attributes={'fill': color, 'font-weight': 'bold', 'font-size': '20px'}
        ).add_to(m)



    folium.Marker(coords[0], popup="Start",
                  icon=folium.Icon(icon='bicycle', color='green', prefix='fa')).add_to(m)
    folium.Marker(coords[-1], popup="End",
                  icon=folium.Icon(icon='flag', color='red', prefix='fa')).add_to(m)
    color_scale.add_to(m)
    m.fit_bounds([[min(p[0] for p in coords), min(p[1] for p in coords)],
                  [max(p[0] for p in coords), max(p[1] for p in coords)]])
    m.save(os.path.join(output_dir, f"{critname}_crit_{year}_map.html"))

    def is_clockwise(coords):
        # Shoelace formula to compute signed area
        area = 0
        for i in range(len(coords)):
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[(i + 1) % len(coords)]
            area += (lon2 - lon1) * (lat2 + lat1)
        return area > 0  # Positive = clockwise in this coordinate system

    direction_str = "Clockwise" if is_clockwise(lap_coords) else "Counter-Clockwise"

    # Elevation JSON
    cumulative_dist = [0]
    for i in range(1, len(coords)):
        cumulative_dist.append(cumulative_dist[-1] + geodesic(coords[i - 1], coords[i]).meters)
    cumulative_dist = [d / 1609.34 for d in cumulative_dist]  # in miles

    elevation_data = {
        "distance_miles": cumulative_dist,
        "elevation_feet": smoothed.tolist()
    }
    with open(os.path.join(output_dir, f"{critname}_crit_{year}_elevation_data.json"), "w") as f:
        json.dump(elevation_data, f, indent=2)

    # Stats
    total_dist = sum(geodesic(coords[i], coords[i + 1]).meters for i in range(len(coords) - 1))
    gradients = []
    for i in range(len(coords) - 1):
        elev_diff = elevs[i + 1] - elevs[i]
        dist = geodesic(coords[i], coords[i + 1]).meters
        if dist > 0:
            gradients.append((elev_diff / dist) * 100)

    # Elevation gain (only positive gains)
    elevation_gain = sum(max(0, elevs[i+1] - elevs[i]) for i in range(len(elevs) - 1))

    # Climb density (meters climbed per kilometer)
    lap_distance_km = total_dist / 1000
    climb_density = elevation_gain / lap_distance_km if lap_distance_km else 0

    stats = {
        "Lap Distance (km)": f"{total_dist / 1000:.2f}",
        "Lap Distance (mi)": f"{total_dist / 1609.34:.2f}",
        "Average Gradient (%)": f"{np.mean(gradients):.2f}",
        "Max Gradient (%)": f"{np.max(gradients):.2f}",
        "Min Gradient (%)": f"{np.min(gradients):.2f}",
        "Elevation Gain (m)": f"{elevation_gain:.0f}",
        "Elevation Gain (ft)": f"{elevation_gain* 3.28084:.0f}",
        "Climb Density (m/km)": f"{climb_density:.1f}",
        "State": state
    }
    
    print(state)
    with open(os.path.join(output_dir, f"{critname}_crit_{year}_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    # HTML Output
    html_file = os.path.join(output_dir, f"{critname}_crit_{year}_details.html")
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{critname} Crit {year} - Course Details</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.2/dist/css/bootstrap.min.css" />
  <link rel="stylesheet" href="../../style.css" />
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body {{ background-color: #F8F9FA; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
    .top-bar {{ margin-bottom: 2rem; }}
    .section {{ position: relative; margin-bottom: 40px; }}
    .section-title {{ font-size: 1.5rem; font-weight: 600; margin-bottom: 15px; border-bottom: 2px solid #DEE2E6; padding-bottom: 5px; }}
    iframe {{ width: 100%; height: 400px; border: none; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }}
    .stat-card {{ background-color: #F8F9FA; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }}
  </style>
</head>
<body>
  <div class="container py-5">
    <div class="d-flex justify-content-between align-items-center top-bar">
      <a href="/index.html" class="btn btn-outline-primary">← Home</a>
      <a href="../../courses/{critname}_{year}/{critname}_crit_{year}.gpx" class="btn btn-outline-secondary" download>Download GPX</a>
    </div>
    <h1 class="text-center mb-4">{critname} Crit {year}</h1>
    <div class="section">
      <div class="section-title">Course Map <small class="text-muted" style="font-size: 0.9rem;">({direction_str})</small></div>
      <iframe src="{critname}_crit_{year}_map.html" loading="lazy"></iframe>
    </div>
    <div class="section">
      <div class="section-title">Elevation Profile</div>
      <div id="elevation-chart" style="height: 400px;"></div>
    </div>
    <div class="section">
      <div class="section-title">Course Statistics</div>
      <div id="stats-container" class="stats-grid"></div>
    </div>
    <script>
      fetch('{critname}_crit_{year}_stats.json')
        .then(res => res.json())
        .then(data => {{
          const stats = [
            {{ label: 'Lap Distance', value: `${{data['Lap Distance (km)']}} km / ${{data['Lap Distance (mi)']}} mi` }},
            {{ label: 'Elevation Gain', value: `${{data['Elevation Gain (m)']}} m / ${{data['Elevation Gain (ft)']}} ft` }},
            {{ label: 'Max Gradient', value: `${{data['Max Gradient (%)']}}%` }},
            {{ label: 'Min Gradient', value: `${{data['Min Gradient (%)']}}%` }}            
          ];
          const container = document.getElementById('stats-container');
          stats.forEach(stat => {{
            const card = document.createElement('div');
            card.className = 'stat-card';
            card.innerHTML = `<p><strong>${{stat.value}}</strong></p><p>${{stat.label}}</p>`;
            container.appendChild(card);
          }});
        }});

      fetch('{critname}_crit_{year}_elevation_data.json')
        .then(res => res.json())
        .then(data => {{
          Plotly.newPlot('elevation-chart', [{{
            x: data.distance_miles,
            y: data.elevation_feet,
            type: 'scatter',
            mode: 'lines',
            fill: 'tozeroy',
            line: {{ color: '#888' }},
            hoverinfo: 'skip'
          }}], {{
            margin: {{ t: 30, r: 10, b: 40, l: 50 }},
            xaxis: {{ title: 'Distance (miles)', fixedrange: true }},
            yaxis: {{
              title: 'Elevation (ft)',
              fixedrange: true,
              automargin: true,
              range: [
                Math.min(...data.elevation_feet) - 5,
                Math.max(...data.elevation_feet) + 5
              ]
            }},
            showlegend: false,
            plot_bgcolor: '#F8F9FA',
            paper_bgcolor: '#F8F9FA'
          }}, {{
            displayModeBar: false,
            staticPlot: true,
            responsive: true
          }});
        }});
    </script>
  </div>
</body>
</html>"""

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
