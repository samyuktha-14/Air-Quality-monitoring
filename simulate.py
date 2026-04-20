import time
import random
import requests
from datetime import datetime

API_URL = "http://127.0.0.0:5000/api/measurements" # 0.0.0.0 resolves to 127.0.0.1 mostly, but let's use localhost
API_URL = "http://127.0.0.1:5000/api/measurements"

# Based on seed data in init_db.py
STATIONS = [1, 2, 3] # Anand Vihar, Bandra, Indiranagar
POLLUTANTS = [1, 2, 3, 4, 5, 6] # PM2.5, PM10, CO, O3, NO2, SO2

def simulate_data():
    print("Starting AQI Data Simulator...")
    print("Press Ctrl+C to stop.")
    
    while True:
        station_id = random.choice(STATIONS)
        pollutant_id = random.choice(POLLUTANTS)
        
        # Generate realistic random values based on pollutant
        if pollutant_id == 1: # PM2.5 (0-500)
            value = round(random.uniform(10.0, 480.0), 2)
        elif pollutant_id == 2: # PM10 (0-600)
            value = round(random.uniform(20.0, 550.0), 2)
        elif pollutant_id == 3: # CO (0-50)
            value = round(random.uniform(0.5, 45.0), 2)
        elif pollutant_id == 4: # O3 (0-1000)
            value = round(random.uniform(10.0, 600.0), 2)
        elif pollutant_id == 5: # NO2 (0-600)
            value = round(random.uniform(5.0, 400.0), 2)
        else: # SO2 (0-2000)
            value = round(random.uniform(10.0, 1000.0), 2)
            
        payload = {
            "station_id": station_id,
            "measured_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "pollutants": {
                pollutant_id: value
            }
        }
        
        try:
            res = requests.post(API_URL, json=payload)
            if res.status_code == 201:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Inserted: Station {station_id}, Pollutant {pollutant_id}, Value {value}")
            else:
                print(f"Error inserting: {res.text}")
        except requests.exceptions.ConnectionError:
            print("Could not connect to API. Is Flask running?")
            
        # Wait before inserting next data
        time.sleep(random.randint(5, 10))

if __name__ == "__main__":
    simulate_data()
