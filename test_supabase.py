"""Quick test to verify Supabase connection and data fetch"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests

SUPABASE_URL = "https://ohwmquomashztbjqeqcn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9od21xdW9tYXNoenRianFlcWNuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNjI1ODAsImV4cCI6MjA5MDYzODU4MH0.C6K9GiEk4eZtcDswzHTd8-Ki3tT0d-0aobw4xOt-jjY"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

print("=" * 50)
print("  Supabase Connection Test")
print("=" * 50)

# Test 1: Fetch all contacts
print("\n[CONTACTS] Family Members (all rows):")
r = requests.get(f"{SUPABASE_URL}/rest/v1/family_members", headers=headers, params={"select": "*"}, timeout=10)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    if data:
        for row in data:
            print(f"  - {row.get('name')} | {row.get('phone')} | email: {row.get('user_email')}")
    else:
        print("  (empty table)")
else:
    print(f"  Error: {r.text}")

# Test 2: Fetch all safe locations
print("\n[LOCATIONS] Safe Locations (all rows):")
r = requests.get(f"{SUPABASE_URL}/rest/v1/safe_locations", headers=headers, params={"select": "*"}, timeout=10)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    if data:
        for row in data:
            print(f"  - {row.get('name')} | ({row.get('latitude')}, {row.get('longitude')}) | email: {row.get('user_email')}")
    else:
        print("  (empty table)")
else:
    print(f"  Error: {r.text}")

print("\n" + "=" * 50)
