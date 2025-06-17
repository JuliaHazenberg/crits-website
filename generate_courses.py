import os
import re
import json
import gpxpy
import folium
from datetime import datetime
from collections import defaultdict
from templates import details_template, frontcard_template
from bs4 import BeautifulSoup

# ---- CONFIG ----
BASE_DIR      = os.path.dirname(__file__)
GPX_DIR       = os.path.join(BASE_DIR, "gpx_files")
OUTPUT_DIR    = os.path.join(BASE_DIR, "courses")
INDEX_HTML    = os.path.join(BASE_DIR, "index.html")
CALENDAR_HTML = os.path.join(BASE_DIR, "calendar.html")
EVENT_MAP_HTML= os.path.join(BASE_DIR, "event_map.html")
EVENTS_JSON   = os.path.join(BASE_DIR, "data", "events.json")

# ensure output
os.makedirs(OUTPUT_DIR, exist_ok=True)

# gpx filename pattern
pattern = re.compile(r"(?P<critname>.+?)_crit_(?P<year>\d{4})\.gpx")

# helpers
def fix_case(raw):
    special = {"ToAD","CBR"}
    return " ".join(w if w in special else w.capitalize() for w in raw.replace("_"," ").split())

def get_start_point(path):
    with open(path, encoding="utf-8") as f:
        g = gpxpy.parse(f)
    if g.tracks and g.tracks[0].segments[0].points:
        p = g.tracks[0].segments[0].points[0]
        return p.latitude, p.longitude
    if g.routes and g.routes[0].points:
        p = g.routes[0].points[0]
        return p.latitude, p.longitude
    return None

# collect everything
course_info = []
states = set()
crit_locations = []

for fn in os.listdir(GPX_DIR):
    if not fn.endswith(".gpx"): continue
    m = pattern.match(fn)
    if not m:
        print("Skipping invalid:", fn)
        continue

    raw, year = m.group("critname"), m.group("year")
    nice = fix_case(raw)
    folder = f"{raw}_{year}"
    gp = os.path.join(GPX_DIR, fn)
    od = os.path.join(OUTPUT_DIR, folder)
    os.makedirs(od, exist_ok=True)

    # generate details + frontcard
    details_template.process_course(gpx_path=gp, output_dir=od, critname=raw, year=year)
    frontcard_template.process_frontcard(gpx_path=gp, output_dir=od, critname=raw, year=year)

    # load stats for state
    with open(os.path.join(od, f"{raw}_crit_{year}_stats.json"), encoding="utf-8") as sf:
        st = json.load(sf).get("State","Unknown").replace(" ","_")
    states.add(st)

    # grab start for event map
    sp = get_start_point(gp)
    if sp:
        crit_locations.append({
            "name": nice,
            "year": year,
            "lat": sp[0],
            "lon": sp[1],
            "folder": folder,
            "raw": raw
        })

    course_info.append({
        "folder": folder,
        "nice": nice,
        "raw": raw,
        "year": year,
        "state": st
    })

# sort
course_info.sort(key=lambda c: c["nice"].lower())

# --- INDEX.HTML ---
cards = []
for c in course_info:
    cards.append(f"""
    <a href="courses/{c['folder']}/{c['raw']}_crit_{c['year']}_details.html"
       class="course-card" data-state="{c['state']}">
      <div class="card-header">
        <h3 class="card-title">{c['nice']} Crit</h3>
        <p class="card-year">{c['year']}</p>
      </div>
      <div class="card-map">
        <iframe src="courses/{c['folder']}/{c['raw']}_crit_{c['year']}_frontcard.html"
                loading="lazy"></iframe>
      </div>
    </a>
    """)

with open(INDEX_HTML, "w", encoding="utf-8") as f:
    f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Crit Courses</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>Crit Courses</h1>
    <nav>
      <a href="index.html">Courses</a>
      <a href="calendar.html">Event Calendar</a>
      <a href="event_map.html">Event Map</a>
    </nav>
  </header>

  <div class="filter-bar">
    <label>Filter by State:</label>
    <select id="stateFilter">
      <option value="all">All</option>
      {''.join(f'<option value="{s}">{s.replace("_"," ")}</option>' for s in sorted(states))}
    </select>
  </div>

  <main class="card-container">
    {''.join(cards)}
  </main>

  <script>
    document.getElementById('stateFilter').addEventListener('change', e => {{
      const sel = e.target.value;
      document.querySelectorAll('.course-card').forEach(c => {{
        c.style.display = sel==='all' || c.dataset.state===sel ? '' : 'none';
      }});
    }});
  </script>

  <footer style="text-align: center; padding: 1em; font-size: 0.8em; color: gray;">
    © 2025 Julia Hazenberg. All rights reserved. For informational purposes only.
  </footer>
</body>
</html>""")

print("✅ index.html generated")

# --- CALENDAR.HTML ---
# load events.json
events = json.load(open(EVENTS_JSON, encoding="utf-8")) if os.path.exists(EVENTS_JSON) else []
by_month = defaultdict(list)
all_states_cal = set()
for e in events:
    by_month[e["date"]].append(e)
    all_states_cal.add(e.get("state","Unknown").replace(" ","_"))

month_order = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]
today_month = datetime.now().strftime("%B")

month_cards = []
for m in month_order:
    highlight = " current-month" if m==today_month else ""
    items = by_month.get(m, [])
    if items:
        lis = "".join(
            f'<li data-state="{ev.get("state","Unknown")}">{ev["critname"]}</li>'
            for ev in sorted(items, key=lambda x: x["critname"])
        )
        month_cards.append(f'<div class="month-card{highlight}"><h2>{m}</h2><ul>{lis}</ul></div>')
    else:
        month_cards.append(f'<div class="month-card{highlight}"><h2>{m}</h2><p>No events</p></div>')

with open(CALENDAR_HTML, "w", encoding="utf-8") as f:
    f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Event Calendar</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>Event Calendar</h1>
    <nav>
      <a href="index.html">Courses</a>
      <a href="calendar.html">Event Calendar</a>
      <a href="event_map.html">Event Map</a>
    </nav>
  </header>

  <div class="filter-bar">
    <label>Filter by State:</label>
    <select id="calStateFilter">
      <option value="all">All</option>
      {''.join(f'<option value="{s}">{s.replace("_"," ")}</option>' for s in sorted(all_states_cal))}
    </select>
  </div>

  <main><div class="calendar-grid">
    {''.join(month_cards)}
  </div></main>

  <script>
    document.getElementById('calStateFilter').addEventListener('change', e => {{
      const sel = e.target.value;
      document.querySelectorAll('.month-card').forEach(mc => {{
        mc.querySelectorAll('li').forEach(li => {{
          li.style.display = sel==='all' || li.dataset.state===sel ? '' : 'none';
        }});
      }});
    }});
  </script>

  <footer style="text-align: center; padding: 1em; font-size: 0.8em; color: gray;">
    © 2025 Julia Hazenberg. All rights reserved. For informational purposes only.
  </footer>
</body>
</html>""")

print("✅ calendar.html generated")

# --- EVENT_MAP.HTML ---

# Create simple map centered on USA with markers for all crit locations
m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="OpenStreetMap")

for loc in crit_locations:
    folium.Marker(
        [loc["lat"], loc["lon"]],
        popup=f'{loc["name"]} {loc["year"]}',
        icon=folium.Icon(color="blue", icon="bicycle", prefix="fa")
    ).add_to(m)

# Render the full folium HTML as a string
full_map_html = m.get_root().render()

# Use BeautifulSoup to extract the map <div> and related styles/scripts
from bs4 import BeautifulSoup

soup = BeautifulSoup(full_map_html, "html.parser")

# Folium map container div (usually with class 'folium-map')
map_div = soup.find("div", class_="folium-map")

# Folium includes <style> and <script> in <head> and <body>, we want to keep them
# Extract folium's <style> and <script> tags (if any)
head_styles = soup.find_all("style")
body_scripts = soup.find_all("script")

# Compose your own HTML wrapping the extracted map div with your CSS linked
event_map_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Event Map</title>
  <link rel="stylesheet" href="style.css" />
  {"".join(str(s) for s in head_styles)}
</head>
<body>
  <header>
    <h1>Event Map</h1>
    <nav>
      <a href="index.html">Courses</a>
      <a href="calendar.html">Event Calendar</a>
      <a href="event_map.html">Event Map</a>
    </nav>
  </header>
  
  <main>
    <div class="map-wrapper">
      {str(map_div)}
    </div>
  </main>

  {"".join(str(s) for s in body_scripts)}

  <footer style="text-align:center; padding:1em; font-size:0.8em; color:gray;">
    © 2025 Julia Hazenberg. All rights reserved. For informational purposes only.
  </footer>
</body>
</html>
"""

with open(EVENT_MAP_HTML, "w", encoding="utf-8") as f:
    f.write(event_map_page)

print("✅ event_map.html generated with wrapper and CSS")
