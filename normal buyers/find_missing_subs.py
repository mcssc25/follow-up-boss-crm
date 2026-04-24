import csv
import re
from collections import Counter

# 1. Read the deployed index.html to find existing subdivisions
index_path = r"c:\Users\daved\AntiGravity Projects\follow up boss\normal buyers\deploy\index.html"
with open(index_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Try to extract names. Let's look for name: "..." or title: "..."
existing_names = set(re.findall(r'name:\s*["\']([^"\']+)["\']', content))
if not existing_names:
    existing_names = set(re.findall(r'title:\s*["\']([^"\']+)["\']', content))

print(f"Found {len(existing_names)} existing subdivisions in index.html")
# print("Existing:", existing_names)

# 2. Read the full CSV to find ALL subdivisions and their counts
csv_path = r"C:\Users\daved\AntiGravity Projects\follow up boss\normal buyers\Default_MLS_Defined_Spreadsheet (1).csv"

subdivisions = []
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        sub = row.get('Subdivision', '').strip()
        city = row.get('City', '').strip()
        # We only want Gulf Shores
        if sub and city.lower() == 'gulf shores':
            subdivisions.append(sub)

counts = Counter(subdivisions)

# 3. Filter out the ones we already have
missing = []
for sub, count in counts.most_common():
    # Basic string matching, lowercasing to be safe
    # We might have slight variations like "Aventura" vs "Aventura Phase 1"
    is_mapped = False
    for existing in existing_names:
        if sub.lower() in existing.lower() or existing.lower() in sub.lower():
            is_mapped = True
            break
    
    if not is_mapped:
        missing.append((sub, count))

print("\nTop Missing Subdivisions in Gulf Shores (by number of listings):")
for sub, count in missing[:30]:
    print(f"- {sub} ({count} listings)")

