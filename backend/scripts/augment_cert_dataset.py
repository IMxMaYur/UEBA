"""
augment_cert_dataset.py
-----------------------
Injects highly realistic synthetic footprints into the CERT dataset to natively 
support 'Impossible Travel' and 'Brute Force' ML detection natively.

This script reads the original `logon.csv`, injects edge-network data (like
failed logins, foreign IP addresses, and GPS coordinates), and outputs an
`augmented_logon.csv` file.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import random
import uuid
from datetime import datetime, timedelta

DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "Dataset"

def get_random_date(start_year=2010, end_year=2011):
    start = datetime(start_year, 1, 2)
    end = datetime(end_year, 5, 16)
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + timedelta(seconds=random_second)

def generate_brute_force(user_id="SIM_BRUTE", count=47, timestamp=None):
    """Generate rapid failed login attempts from a malicious IP."""
    if not timestamp:
        timestamp = get_random_date()
    
    rows = []
    # e.g. Tor Exit Node
    ip = "185.220.101.45"
    country = "Netherlands"
    
    for i in range(count):
        # 47 attempts inside a tight 3 minute window
        attempt_time = timestamp + timedelta(seconds=random.randint(1, 180))
        rows.append({
            "id": f"{{{uuid.uuid4()}}}",
            "date": attempt_time.strftime("%m/%d/%Y %H:%M:%S"),
            "user": user_id,
            "pc": "PC-EXT-FIREWALL", # edge gateway
            "activity": "Failed_Logon",
            "ip": ip,
            "country": country,
            "latitude": 52.1326,
            "longitude": 5.2913
        })
    return rows

def generate_impossible_travel(user_id="SIM_TRAVEL", timestamp=None):
    """Generate two logins from geographically distant locations in short succession."""
    if not timestamp:
        timestamp = get_random_date()
        
    rows = []
    # 1. Login from London, UK
    rows.append({
        "id": f"{{{uuid.uuid4()}}}",
        "date": timestamp.strftime("%m/%d/%Y %H:%M:%S"),
        "user": user_id,
        "pc": "PC-LONDON-OFFICE",
        "activity": "Logon",
        "ip": "82.163.43.12",
        "country": "United Kingdom",
        "latitude": 51.5074,
        "longitude": -0.1278
    })
    
    # 2. Login 30 minutes later from Beijing, China
    impossible_time = timestamp + timedelta(minutes=30)
    rows.append({
        "id": f"{{{uuid.uuid4()}}}",
        "date": impossible_time.strftime("%m/%d/%Y %H:%M:%S"),
        "user": user_id,
        "pc": "PC-BEIJING-VPN",
        "activity": "Logon",
        "ip": "223.73.102.11",
        "country": "China",
        "latitude": 39.9042,
        "longitude": 116.4074
    })
    return rows

def augment():
    original_logon = DATASET_DIR / "logon.csv"
    augmented_logon = DATASET_DIR / "augmented_logon.csv"
    
    print(f"Reading original {original_logon.name} (this might take a minute)...")
    try:
        df = pd.read_csv(original_logon)
    except FileNotFoundError:
        print(f"Error: {original_logon} not found.")
        return
        
    # Append NA columns if they don't exist
    for c in ["ip", "country", "latitude", "longitude"]:
        if c not in df.columns:
            df[c] = np.nan
            
    print("Generating Brute Force signatures...")
    bf_rows = generate_brute_force(user_id="WTC0042", count=60) # Target a random legacy user
    bf_rows.extend(generate_brute_force(user_id="RGM0043", count=120))
    bf_rows.extend(generate_brute_force(user_id="SIM_BRUTE", count=47))
    
    print("Generating Impossible Travel signatures...")
    travel_rows = generate_impossible_travel(user_id="WTC0042")
    travel_rows.extend(generate_impossible_travel(user_id="HXL0041"))
    travel_rows.extend(generate_impossible_travel(user_id="SIM_TRAVEL"))
    
    synthetic_df = pd.DataFrame(bf_rows + travel_rows)
    print(f"Injecting {len(synthetic_df)} heavily anomalous rows...")
    
    # Concat
    final_df = pd.concat([df, synthetic_df], ignore_index=True)
    
    # Sort chronologically
    print("Sorting chronologically to ensure pipeline integrity...")
    final_df["sort_date"] = pd.to_datetime(final_df["date"], format="%m/%d/%Y %H:%M:%S", errors="coerce")
    final_df = final_df.sort_values(by="sort_date")
    final_df = final_df.drop(columns=["sort_date"])
    
    print(f"Writing to {augmented_logon} ...")
    final_df.to_csv(augmented_logon, index=False)
    print("Done! You can now update data_loader.py to point to augmented_logon.csv.")

if __name__ == "__main__":
    augment()
