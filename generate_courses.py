import os
import re
from templates import details_template, frontcard_template
import json

# Paths
BASE_DIR = os.path.dirname(__file__)
GPX_DIR = os.path.join(BASE_DIR, "gpx_files")
OUTPUT_DIR = os.path.join(BASE_DIR, "courses")
INDEX_HTML = os.path.join(BASE_DIR, "index.html")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Pattern: e.g., "elmhurst_crit_2024.gpx"
pattern = re.compile(r"(?P<critname>.+?)_crit_(?P<year>\d{4})\.gpx")

# Store course info for index.html
course_info_list = []  # Will hold dicts with all info for sorting
states = set()  # Collect unique states

# Function to maintain case for specific words
def fix_case(critname_raw):
    special_case_words = ['ToAD', 'CBR']
    critname = ' '.join(
        word if word in special_case_words else word.capitalize()
        for word in critname_raw.replace('_', ' ').split()
    )
    return critname

# Scan for .gpx files
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

    # if not os.path.exists(output_subdir):
    #     print(f"Processing: {folder_name}")
    #     os.makedirs(output_subdir)

    #     # Generate Course Details HTML
    #     details_template.process_course(
    #         gpx_path=gpx_path,
    #         output_dir=output_subdir,
    #         critname=critname_raw,
    #         year=year
    #     )

    #     # Generate Frontcard HTML
    #     frontcard_template.process_frontcard(
    #         gpx_path=gpx_path,
    #         output_dir=output_subdir,
    #         critname=critname_raw,
    #         year=year
    #     )

    print(f"Processing: {folder_name}")
    os.makedirs(output_subdir, exist_ok=True)
    
    # Always regenerate course details
    details_template.process_course(
        gpx_path=gpx_path,
        output_dir=output_subdir,
        critname=critname_raw,
        year=year
    )
    
    # Always regenerate frontcard
    frontcard_template.process_frontcard(
        gpx_path=gpx_path,
        output_dir=output_subdir,
        critname=critname_raw,
        year=year
    )

    stats_path = os.path.join(output_subdir, f"{critname_raw}_crit_{year}_stats.json")
    with open(stats_path, encoding="utf-8") as stats_file:
        stats = json.load(stats_file)
        state = stats.get("State", "Unknown").replace(" ", "_")
        states.add(state)

    course_info_list.append({
        "folder_name": folder_name,
        "critname": critname,
        "critname_raw": critname_raw,
        "year": year,
        "state": state,
    })

# Sort courses alphabetically by critname (case-insensitive)
course_info_list.sort(key=lambda x: x["critname"].lower())

# Generate HTML cards after sorting
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

# Generate index.html with filter dropdown and JS
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
    © 2025 Julia Hazenberg. All rights reserved. The information on this website is for general informational purposes only and subject to change.
     </footer>
</body>
</html>""")

print("✅ index.html generated.")
