import pandas as pd
import requests
from datetime import datetime
import json
import os
from bs4 import BeautifulSoup

# Constants
RACE_DATE = "2024-03-09"
RACE_NAME = "Saudi Arabian Grand Prix"
F1_BASE_URL = "https://www.formula1.com/en/results/2024/races/1230/saudi-arabia"

def fetch_f1_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return BeautifulSoup(response.text, 'html.parser')
    return None

def fetch_qualifying_data():
    qualifying_url = f"{F1_BASE_URL}/qualifying.html"
    soup = fetch_f1_page(qualifying_url)
    qualifying_data = []

    if soup:
        table = soup.find('table', {'class': 'resultsarchive-table'})
        if table:
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    qualifying_data.append({
                        'Position': cols[0].text.strip(),
                        'Driver': cols[2].text.strip(),
                        'Team': cols[3].text.strip(),
                        'Q1': cols[4].text.strip(),
                        'Q2': cols[5].text.strip() if len(cols) > 5 else 'No Time',
                        'Q3': cols[6].text.strip() if len(cols) > 6 else 'No Time',
                        'Laps': cols[7].text.strip()
                    })
    return pd.DataFrame(qualifying_data) if qualifying_data else None

def fetch_practice_data(session):
    practice_url = f"{F1_BASE_URL}/practice-{session}.html"
    soup = fetch_f1_page(practice_url)
    practice_data = []

    if soup:
        table = soup.find('table', {'class': 'resultsarchive-table'})
        if table:
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 7:
                    practice_data.append({
                        'Position': cols[0].text.strip(),
                        'Driver': cols[2].text.strip(),
                        'Team': cols[3].text.strip(),
                        'Time': cols[4].text.strip(),
                        'Gap': cols[5].text.strip(),
                        'Laps': cols[6].text.strip()
                    })
    return pd.DataFrame(practice_data) if practice_data else None

def fetch_lap_times():
    lap_times_url = f"{F1_BASE_URL}/race-result.html"
    soup = fetch_f1_page(lap_times_url)
    lap_times_data = []

    if soup:
        table = soup.find('table', {'class': 'resultsarchive-table'})
        if table:
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    driver = cols[2].text.strip()
                    fastest_lap = cols[6].text.strip()
                    lap_times_data.append({
                        'Driver': driver,
                        'Position': cols[0].text.strip(),
                        'FastestLap': fastest_lap,
                        'FastestLapTime': cols[5].text.strip(),
                        'TotalTime': cols[4].text.strip(),
                        'Points': cols[7].text.strip()
                    })
    return pd.DataFrame(lap_times_data) if lap_times_data else None

def fetch_tire_data():
    tire_url = f"{F1_BASE_URL}/pit-stop-summary.html"
    soup = fetch_f1_page(tire_url)
    tire_data = []

    if soup:
        table = soup.find('table', {'class': 'resultsarchive-table'})
        if table:
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 5:
                    tire_data.append({
                        'Driver': cols[1].text.strip(),
                        'Stop': cols[0].text.strip(),
                        'Lap': cols[2].text.strip(),
                        'Time': cols[3].text.strip(),
                        'Duration': cols[4].text.strip()
                    })
    return pd.DataFrame(tire_data) if tire_data else None

def save_data():
    # Fetch and save qualifying data
    qualifying_df = fetch_qualifying_data()
    if qualifying_df is not None:
        qualifying_df.to_csv('saudi_gp_2024_qualifying.csv', index=False)
        print("Qualifying data saved")

    # Fetch and save practice session data
    for session in range(1, 4):
        practice_df = fetch_practice_data(session)
        if practice_df is not None:
            practice_df.to_csv(f'saudi_gp_2024_practice{session}.csv', index=False)
            print(f"Practice {session} data saved")

    # Fetch and save lap times data
    lap_times_df = fetch_lap_times()
    if lap_times_df is not None:
        lap_times_df.to_csv('saudi_gp_2024_race_results.csv', index=False)
        print("Race results data saved")

    # Fetch and save tire data
    tire_df = fetch_tire_data()
    if tire_df is not None:
        tire_df.to_csv('saudi_gp_2024_tire_data.csv', index=False)
        print("Tire data saved")

if __name__ == "__main__":
    print(f"Fetching detailed data for {RACE_NAME} {RACE_DATE}")
    save_data()
    print("Data collection complete")
