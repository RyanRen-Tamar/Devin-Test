import requests
import pandas as pd
from datetime import datetime

# Constants
RACE_DATE = "2024-03-09"
RACE_NAME = "Saudi Arabian Grand Prix"
API_BASE_URL = "https://api.formula1.com/v1/event-tracker"

def fetch_tire_data():
    """Fetch tire compound data for each stint"""
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
    }

    tire_data = []
    try:
        # Note: This is a placeholder structure as F1's actual API requires authentication
        response = requests.get(f"{API_BASE_URL}/2024/2/race", headers=headers)
        if response.status_code == 200:
            data = response.json()
            for driver in data['raceData']['drivers']:
                for stint in driver['stints']:
                    tire_data.append({
                        'Driver': driver['name'],
                        'Stint': stint['number'],
                        'Compound': stint['compound'],
                        'Start_Lap': stint['startLap'],
                        'End_Lap': stint['endLap'],
                        'Laps': stint['laps']
                    })
        return pd.DataFrame(tire_data)
    except Exception as e:
        print(f"Error fetching tire data: {e}")
        return None

def fetch_sector_times():
    """Fetch sector times for each lap"""
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
    }

    sector_data = []
    try:
        response = requests.get(f"{API_BASE_URL}/2024/2/race/sectors", headers=headers)
        if response.status_code == 200:
            data = response.json()
            for lap in data['sectorTimes']:
                for driver in lap['drivers']:
                    sector_data.append({
                        'Driver': driver['name'],
                        'Lap': lap['number'],
                        'Sector1': driver['sector1'],
                        'Sector2': driver['sector2'],
                        'Sector3': driver['sector3']
                    })
        return pd.DataFrame(sector_data)
    except Exception as e:
        print(f"Error fetching sector times: {e}")
        return None

def save_data():
    """Save tire and sector data to CSV files"""
    tire_df = fetch_tire_data()
    if tire_df is not None:
        tire_df.to_csv('saudi_gp_2024_tire_stints.csv', index=False)
        print("Tire stint data saved")

    sector_df = fetch_sector_times()
    if sector_df is not None:
        sector_df.to_csv('saudi_gp_2024_sector_times.csv', index=False)
        print("Sector times data saved")

if __name__ == "__main__":
    print(f"Fetching tire and sector data for {RACE_NAME} {RACE_DATE}")
    save_data()
    print("Data collection complete")
