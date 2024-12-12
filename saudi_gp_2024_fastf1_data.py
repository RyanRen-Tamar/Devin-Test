import fastf1
import pandas as pd
import os
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create cache directory
cache_dir = Path('f1_cache')
cache_dir.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(cache_dir))

def save_session_data(session, name, data_type):
    """Helper function to safely save session data"""
    try:
        if data_type == 'qualifying':
            df = pd.DataFrame(session.results)[['DriverNumber', 'BroadcastName', 'Abbreviation', 'TeamName', 'Q1', 'Q2', 'Q3']]
            df.to_csv(f'saudi_gp_2024_{data_type}_full.csv', index=False)
        elif data_type == 'practice':
            df = pd.DataFrame(session.results)[['DriverNumber', 'BroadcastName', 'TeamName', 'Time', 'Status']]
            df.to_csv(f'saudi_gp_2024_practice_{name}.csv', index=False)
        elif data_type == 'race':
            # Updated columns based on available data
            df = pd.DataFrame(session.results)[['DriverNumber', 'BroadcastName', 'TeamName', 'Status', 'Points', 'Time', 'Position']]
            df.to_csv(f'saudi_gp_2024_race_results_full.csv', index=False)
        elif data_type == 'laps':
            df = pd.DataFrame(session.laps)[['Driver', 'LapNumber', 'LapTime', 'Compound', 'TyreLife']]
            df.to_csv(f'saudi_gp_2024_lap_times_full.csv', index=False)
        logger.info(f'Successfully saved {data_type} data for {name}')
        return True
    except Exception as e:
        logger.error(f'Error saving {data_type} data for {name}: {str(e)}')
        logger.info(f'Available columns: {session.results.columns.tolist() if hasattr(session.results, "columns") else "No columns found"}')
        return False

def collect_session_data():
    try:
        logger.info('Loading Saudi GP 2024 data...')
        # Load all sessions
        race = fastf1.get_session(2024, 'Saudi Arabia', 'R')
        quali = fastf1.get_session(2024, 'Saudi Arabia', 'Q')
        fp1 = fastf1.get_session(2024, 'Saudi Arabia', 'FP1')
        fp2 = fastf1.get_session(2024, 'Saudi Arabia', 'FP2')
        fp3 = fastf1.get_session(2024, 'Saudi Arabia', 'FP3')

        logger.info('Loading session data...')
        # Load the data for each session
        for session, name in [(race, 'Race'), (quali, 'Qualifying'),
                            (fp1, 'FP1'), (fp2, 'FP2'), (fp3, 'FP3')]:
            try:
                session.load()
                logger.info(f'Successfully loaded {name} session data')
            except Exception as e:
                logger.error(f'Error loading {name} session: {str(e)}')
                continue

        # Save data for each session type
        save_session_data(quali, 'Qualifying', 'qualifying')
        for session, name in [(fp1, 'FP1'), (fp2, 'FP2'), (fp3, 'FP3')]:
            save_session_data(session, name, 'practice')
        save_session_data(race, 'Race', 'race')
        save_session_data(race, 'Race', 'laps')

        logger.info('Data collection complete!')
        return True

    except Exception as e:
        logger.error(f'Error during data collection: {str(e)}')
        return False

if __name__ == '__main__':
    collect_session_data()
