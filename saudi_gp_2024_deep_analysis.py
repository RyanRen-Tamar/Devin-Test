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

def load_data():
    """Load all required data files"""
    data = {}
    try:
        data['lap_times'] = pd.read_csv('saudi_gp_2024_lap_times_full.csv')
        data['results'] = pd.read_csv('saudi_gp_2024_results.csv')
        data['qualifying'] = pd.read_csv('saudi_gp_2024_qualifying_full.csv')
    except FileNotFoundError as e:
        print(f"Warning: Could not load file - {e.filename}")
    return data

def analyze_race_pace_trends(lap_times_df):
    """Analyze race pace trends including stint performance"""
    # Convert lap times to seconds for numerical analysis
    lap_times_df['LapTime'] = pd.to_timedelta(lap_times_df['LapTime']).dt.total_seconds()

    # Calculate moving averages for different window sizes
    plt.figure(figsize=(15, 10))

    for driver in lap_times_df['Driver'].unique()[:5]:  # Top 5 drivers for clarity
        driver_laps = lap_times_df[lap_times_df['Driver'] == driver]

        # Calculate different moving averages
        ma_3 = driver_laps['LapTime'].rolling(window=3).mean()
        ma_10 = driver_laps['LapTime'].rolling(window=10).mean()

        plt.plot(driver_laps['LapNumber'], ma_3, label=f'{driver} (3-lap avg)', alpha=0.7)
        plt.plot(driver_laps['LapNumber'], ma_10, label=f'{driver} (10-lap avg)', linestyle='--', alpha=0.4)

    plt.title('Race Pace Trends - Moving Averages (Top 5 Drivers)')
    plt.xlabel('Lap Number')
    plt.ylabel('Lap Time (seconds)')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig('saudi_gp_2024_race_pace_trends.png')
    plt.close()

def analyze_tire_performance(lap_times_df):
    """Analyze tire performance degradation"""
    # Convert lap times to seconds
    lap_times_df['LapTime'] = pd.to_timedelta(lap_times_df['LapTime']).dt.total_seconds()

    plt.figure(figsize=(15, 8))

    for compound in lap_times_df['Compound'].unique():
        compound_data = lap_times_df[lap_times_df['Compound'] == compound]

        # Calculate average lap time by tire life
        tire_performance = compound_data.groupby('TyreLife')['LapTime'].mean()

        # Plot with confidence interval
        plt.plot(tire_performance.index, tire_performance.values,
                label=f'{compound}', marker='o', markersize=4)

    plt.title('Tire Performance Degradation')
    plt.xlabel('Tire Life (Laps)')
    plt.ylabel('Average Lap Time (seconds)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('saudi_gp_2024_tire_performance.png')
    plt.close()

def analyze_strategic_decisions(lap_times_df, results_df):
    """Analyze strategic decisions and their impact"""
    # Analyze pit stop timing and its effect
    plt.figure(figsize=(15, 8))

    # Get unique compounds for each driver
    driver_strategies = lap_times_df.groupby(['Driver', 'LapNumber'])['Compound'].first().unstack()

    # Plot tire compound changes
    for idx, driver in enumerate(driver_strategies.index[:5]):  # Top 5 drivers
        compounds = driver_strategies.loc[driver].dropna()

        # Create colored segments for different compounds
        for compound in compounds.unique():
            compound_laps = compounds[compounds == compound].index
            plt.plot(compound_laps, [idx] * len(compound_laps),
                    linewidth=10, label=compound if idx == 0 else "_nolegend_")

    plt.yticks(range(5), driver_strategies.index[:5])
    plt.title('Tire Strategy Visualization (Top 5 Drivers)')
    plt.xlabel('Lap Number')
    plt.ylabel('Driver')
    plt.legend(title='Compound', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('saudi_gp_2024_strategy_analysis.png')
    plt.close()

def main():
    # Load data
    data = load_data()

    if 'lap_times' in data and 'results' in data:
        # Perform deep analysis
        analyze_race_pace_trends(data['lap_times'])
        print("Generated race pace trends visualization")

        analyze_tire_performance(data['lap_times'])
        print("Generated tire performance analysis")

        analyze_strategic_decisions(data['lap_times'], data['results'])
        print("Generated strategic decisions analysis")

        print("\nDeep analysis complete! Generated visualization files:")
        print("1. saudi_gp_2024_race_pace_trends.png")
        print("2. saudi_gp_2024_tire_performance.png")
        print("3. saudi_gp_2024_strategy_analysis.png")
    else:
        print("Error: Required data files not found")

if __name__ == "__main__":
    main()
