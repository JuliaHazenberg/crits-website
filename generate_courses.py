import os
import re
from templates import details_template, frontcard_template
import json
from collections import defaultdict
from datetime import datetime
import gpxpy
import folium

# Paths
BASE_DIR = os.path.dirname(__file__)
GPX_DIR = os.path.join(BASE_DIR, "gpx_files")
OUTPUT_DIR = os.path.join(BASE_DIR, "courses")
INDEX_HTML = os.path.join(BASE_DIR, "index.html")
CALENDAR_HTML = os.path.join(BASE_DIR, "calendar.html")
EVENTS_JSON = os.path.join(BASE_DIR, "data", "events.json")
EVENT_MAP_HTML = os.path.join(BASE_DIR, "event_map.html")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Pattern: e.g., "elmhurst_crit_2024.gpx"
pattern = re.compile(r"(?P<critname>.+?)_crit_(?P<year>\d{4})\.gpx")

# Store course info for index.html
course_info_list = []
states = set()
crit_locations = []  # For event map markers

def fix_case(critname_raw):
    special_case_words = ['ToAD', 'CBR']
    critname = ' '.join(
        word if word in special_case_words else word.capitalize()
        for word in critname_raw.replace('_', ' ').split()
    )
    return critname

def get_start_point(gpx_path):
    with open(gpx_path, encoding="utf-8") as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    if gpx.tracks and gpx.tracks[0].segments and gpx.tracks[0].segments[0].points:
        first_point = gpx.tracks[0].segments[0].points[0]
        return (first_point.latitude, first_point.longitude)
    elif gpx.routes and gpx.routes[0].points:
        first_point = gpx.routes[0].points[0]
        return (first_point.latitude, first_point.longitude)
    else:
        return None

def generate_event_map(crit_locations, output_path):
    # Center map on US roughly
    m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="OpenStreetMap")

    for crit in crit_locations:
        popup_html = f'<a href="courses/{crit["folder"]}/{crit["critname_raw"]}_crit_{crit["year"]}_details.html" target="_blank">{crit["name"]} {crit["year"]}</a>'
        folium.Marker(
            location=[crit["lat"], crit["lon"]],
            popup=popup_html,
            icon=folium.Icon(color="blue", icon="bicycle", prefix='fa')
        ).add_to(m)

    m.save(output_path)
    print(f"✅ Event map saved to {output_path}")

# Process all GPX files
for filename in os.listdir(GPX_DIR):
    if not filename.endswith(".gpx"):
        continue

    match = pattern.match(filename)
    if not match:
        print(f"Skipping invalid filename: {filename}")
        continue

    critname_raw = match.group("critname")
    year = match.group("year")
    critname = fix_case(critname_raw)

    folder_name = f"{critname_raw}_{year}"
    gpx_path = os.path.join(GPX_DIR, filename)
    output_subdir = os.path.join(OUTPUT_DIR, folder_name)

    print(f"Processing: {folder_name}")
    os.makedirs(output_subdir, exist_ok=True)

    # Process details and front card templates (existing code)
    details_template.process_course(
        gpx_path=gpx_path,
        output_dir=output_subdir,
        critname=critname_raw,
        year=year
    )

    frontcard_template.process_frontcard(
        gpx_path=gpx_path,
        output_dir=output_subdir,
        critname=critname_raw,
        year=year
    )

    # Load stats to get state info
    stats_path = os.path.join(output_subdir, f"{critname_raw}_crit_{year}_stats.json")
    with open(stats_path, encoding="utf-8") as stats_file:
        stats = json.load(stats_file)
        state = stats.get("State", "Unknown").replace(" ", "_")
        states.add(state)

    # Extract start coordinates for event map
    start_coords = get_start_point(gpx_path)
    if start_coords:
        crit_locations.append({
            "name": critname,
            "year": year,
            "lat": start_coords[0],
            "lon": start_coords[1],
            "folder": folder_name,
            "critname_raw": critname_raw,
        })

    course_info_list.append({
        "folder_name": folder_name,
        "critname": critname,
        "critname_raw": critname_raw,
        "year": year,
        "state": state,
    })

# Sort and generate index.html with updated nav including Event Map tab
course_info_list.sort(key=lambda x: x["critname"].lower())

course_cards = []
for c in course_info_list:
    course_cards.append(f"""
<a href="courses/{c['folder_name']}/{c['critname_raw']}_crit_{c['year']}_details.html" class="course-card" data-state="{c['state']}">
<div class="card-header">
  <h3 class="card-title">{c['critname']} Crit</h3>
  <p class="card-year">{c['year']}</p>
</div>
<div class="card-map">
  <iframe src="courses/{c['folder_name']}/{c['critname_raw']}_crit_{c['year']}_frontcard.html" loading="lazy"></iframe>
</div>
</a>
""")

with open(INDEX_HTML, "w", encoding="utf-8") as f:
    f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Crit Courses</title>
  <link rel="stylesheet" href="style.css" />
  <style>
    .filter-bar {{
      margin: 1rem;
      text-align: center;
    }}
    .filter-bar select {{
      padding: 0.5rem;
      font-size: 1rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Crit Courses</h1>
    <nav style="text-align: center; margin-bottom: 1rem;">
      <a href="index.html">Courses</a> |
      <a href="calendar.html">Event Calendar</a> |
      <a href="event_map.html">Event Map</a>
    </nav>
  </header>

  <div class="filter-bar">
    <label for="stateFilter">Filter by State:</label>
    <select id="stateFilter">
      <option value="all">All States</option>
      {''.join(f'<option value="{s}">{s.replace("_", " ")}</option>' for s in sorted(states))}
    </select>
  </div>

  <main class="card-container">
    {''.join(course_cards)}
  </main>

  <script>
    const select = document.getElementById('stateFilter');
    const cards = document.querySelectorAll('.course-card');

    select.addEventListener('change', () => {{
      const selected = select.value;
      cards.forEach(card => {{
        if (selected === 'all' || card.dataset.state === selected) {{
          card.style.display = '';
        }} else {{
          card.style.display = 'none';
        }}
      }});
    }});
  </script>
  <footer style="text-align: center; padding: 1em; font-size: 0.8em; color: gray;">
    © 2025 Julia Hazenberg. All rights reserved.
  </footer>
</body>
</html>""")

print("✅ index.html generated.")

# --- CALENDAR GENERATION -----------------------------------------------
if os.path.exists(EVENTS_JSON):
    with open(EVENTS_JSON, encoding="utf-8") as f:
        try:
            events = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Error loading events.json: {e}")
            events = []

    # group events by month
    events_by_month = defaultdict(list)
    all_states = set()
    for e in events:
        month = e["date"]
        state = e.get("state", "Unknown").replace(" ", "_")
        all_states.add(state)
        events_by_month[month].append({
            "critname": e["critname"],
            "state": state
        })

    month_order = ["January","February","March","April","May","June",
                   "July","August","September","October","November","December"]

    # Get current month as string (e.g., "June")
    current_month_name = datetime.now().strftime("%B")

    month_cards = []
    for m in month_order:
        highlight = " current-month" if m == current_month_name else ""
        if m in events_by_month:
            items = "".join(
                f'<li data-state="{ev["state"]}">{ev["critname"]}</li>'
                for ev in sorted(events_by_month[m], key=lambda x: x["critname"])
            )
            month_cards.append(
                f'<div class="month-card{highlight}"><h2>{m}</h2><ul>{items}</ul></div>'
            )
        else:
            # No events this month, still show empty month with placeholder
            month_cards.append(
                f'<div class="month-card{highlight}"><h2>{m}</h2><p> </p></div>'
            )

    sections = "".join(month_cards)  # no extra whitespace

    calendar_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Crit Event Calendar</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <link rel="stylesheet" href="style.css" />
  <style>
    .filter-bar {{
      margin: 1rem;
      text-align: center;
    }}
    .filter-bar select {{
      padding: 0.5rem;
      font-size: 1rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Event Calendar</h1>
    <nav style="text-align: center; margin-bottom: 1rem;">
      <a href="index.html">Courses</a> |
      <a href="calendar.html">Event Calendar</a> |
      <a href="event_map.html">Event Map</a>
    </nav>
  </header>

  <div class="filter-bar">
    <label for="calendarStateFilter">Filter by State:</label>
    <select id="calendarStateFilter">
      <option value="all">All States</option>
      {''.join(f'<option value="{s}">{s.replace("_", " ")}</option>' for s in sorted(all_states))}
    </select>
  </div>

  <main><div class="calendar-grid">{sections}</div></main>

  <script>
    const calendarSelect = document.getElementById('calendarStateFilter');
    const monthCards = document.querySelectorAll('.month-card');

    calendarSelect.addEventListener('change', () => {{
      const selected = calendarSelect.value;
      monthCards.forEach(monthCard => {{
        const items = monthCard.querySelectorAll('li');
        items.forEach(item => {{
          if (selected === 'all' || item.dataset.state === selected) {{
            item.style.display = '';
          }} else {{
            item.style.display = 'none';
          }}
        }});
        // Note: do NOT hide month card itself, so all months remain visible
      }});
    }});
  </script>

  <footer style="text-align: center; padding: 1em; font-size: 0.8em; color: gray;">
    © 2025 Julia Hazenberg. All rights reserved.
  </footer>
</body>
</html>"""

    with open(CALENDAR_HTML, "w", encoding="utf-8") as f:
        f.write(calendar_html)

    print("✅ calendar.html generated.")
else:
    print("⚠️ events.json not found — skipping calendar generation.")

# --- EVENT MAP GENERATION -----------------------------------------------
generate_event_map(crit_locations, EVENT_MAP_HTML)
