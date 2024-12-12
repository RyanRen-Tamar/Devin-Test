import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import timedelta

# Set style for all plots
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = [12, 6]
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12

def load_all_data():
    """Load all collected data files"""
    data = {}
    try:
        data['qualifying'] = pd.read_csv('saudi_gp_2024_qualifying_full.csv')
        data['results'] = pd.read_csv('saudi_gp_2024_results.csv')
        data['lap_times'] = pd.read_csv('saudi_gp_2024_lap_times_full.csv')
        data['fp1'] = pd.read_csv('saudi_gp_2024_practice_FP1.csv')
        data['fp2'] = pd.read_csv('saudi_gp_2024_practice_FP2.csv')
        data['fp3'] = pd.read_csv('saudi_gp_2024_practice_FP3.csv')
    except FileNotFoundError as e:
        print(f"Warning: Could not load file - {e.filename}")
    return data

def analyze_qualifying_performance(quali_data):
    """Analyze qualifying session performance"""
    # Convert time strings to timedelta
    for col in ['Q1', 'Q2', 'Q3']:
        quali_data[col] = pd.to_timedelta(quali_data[col])

    # Create qualifying performance visualization
    plt.figure(figsize=(12, 6))
    teams = quali_data['TeamName'].unique()
    colors = sns.color_palette("husl", len(teams))
    team_colors = dict(zip(teams, colors))

    for idx, row in quali_data.iterrows():
        if pd.notna(row['Q3']):
            plt.scatter(row['TeamName'], row['Q3'].total_seconds(),
                       color=team_colors[row['TeamName']], s=100, label=row['BroadcastName'])

    plt.title('Q3 Times by Team - 2024 Saudi Arabian GP')
    plt.xticks(rotation=45)
    plt.ylabel('Time (seconds)')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('saudi_gp_2024_qualifying_analysis.png')
    plt.close()

def analyze_race_pace(lap_times):
    """Analyze race pace and consistency"""
    # Convert lap times to seconds
    lap_times['LapTime'] = pd.to_timedelta(lap_times['LapTime']).dt.total_seconds()

    # Calculate moving average lap times
    plt.figure(figsize=(15, 8))
    for driver in lap_times['Driver'].unique():
        driver_laps = lap_times[lap_times['Driver'] == driver]
        plt.plot(driver_laps['LapNumber'],
                driver_laps['LapTime'].rolling(window=5).mean(),
                label=driver, alpha=0.7)

    plt.title('5-Lap Moving Average Pace - 2024 Saudi Arabian GP')
    plt.xlabel('Lap Number')
    plt.ylabel('Lap Time (seconds)')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('saudi_gp_2024_race_pace_analysis.png')
    plt.close()

def analyze_tire_strategies(lap_times):
    """Analyze tire compound usage and performance"""
    # Calculate stint lengths for each compound
    tire_stints = lap_times.groupby(['Driver', 'Compound'])['LapNumber'].count().unstack()

    plt.figure(figsize=(12, 6))
    tire_stints.plot(kind='bar', stacked=True)
    plt.title('Tire Compound Usage by Driver - 2024 Saudi Arabian GP')
    plt.xlabel('Driver')
    plt.ylabel('Number of Laps')
    plt.legend(title='Compound')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('saudi_gp_2024_tire_strategy_analysis.png')
    plt.close()

def main():
    # Load all data
    data = load_all_data()

    # Perform analyses based on available data
    if 'qualifying' in data:
        analyze_qualifying_performance(data['qualifying'])
        print("Generated qualifying analysis visualization")

    if 'lap_times' in data:
        analyze_race_pace(data['lap_times'])
        print("Generated race pace analysis visualization")
        analyze_tire_strategies(data['lap_times'])
        print("Generated tire strategy analysis visualization")

    print("\nAnalysis complete! Check the generated visualization files:")
    print("1. saudi_gp_2024_qualifying_analysis.png (if qualifying data was available)")
    print("2. saudi_gp_2024_race_pace_analysis.png (if lap times data was available)")
    print("3. saudi_gp_2024_tire_strategy_analysis.png (if lap times data was available)")

if __name__ == "__main__":
    main()
