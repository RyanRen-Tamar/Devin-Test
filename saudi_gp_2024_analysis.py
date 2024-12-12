import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Race Results Data
race_results = {
    'Position': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    'Driver': ['Max Verstappen', 'Lando Norris', 'Charles Leclerc', 'Oscar Piastri',
              'Carlos Sainz', 'Lewis Hamilton', 'George Russell', 'Sergio Perez',
              'Lance Stroll', 'Yuki Tsunoda', 'Nico Hulkenberg', 'Kevin Magnussen',
              'Daniel Ricciardo', 'Esteban Ocon', 'Zhou Guanyu', 'Pierre Gasly',
              'Logan Sargeant', 'Valtteri Bottas', 'Fernando Alonso', 'Alexander Albon'],
    'Team': ['Red Bull Racing Honda RBPT', 'McLaren Mercedes', 'Ferrari', 'McLaren Mercedes',
            'Ferrari', 'Mercedes', 'Mercedes', 'Red Bull Racing Honda RBPT',
            'Aston Martin Aramco Mercedes', 'RB Honda RBPT', 'Haas Ferrari', 'Haas Ferrari',
            'RB Honda RBPT', 'Alpine Renault', 'Kick Sauber Ferrari', 'Alpine Renault',
            'Williams Mercedes', 'Kick Sauber Ferrari', 'Aston Martin Aramco Mercedes', 'Williams Mercedes'],
    'Laps': [63, 63, 63, 63, 63, 63, 63, 63, 63, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62, 51],
    'Time/Gap': ['1:25:25.252', '+0.725s', '+7.916s', '+14.132s', '+22.325s', '+35.104s',
                '+47.154s', '+54.776s', '+79.556s', '+1 lap', '+1 lap', '+1 lap', '+1 lap',
                '+1 lap', '+1 lap', '+1 lap', '+1 lap', '+1 lap', '+1 lap', 'DNF'],
    'Points': [25, 18, 15, 12, 10, 8, 7, 4, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
}

# Convert to DataFrame
df = pd.DataFrame(race_results)

# Save to CSV
df.to_csv('/home/ubuntu/repos/Devin-Test/saudi_gp_2024_results.csv', index=False)

# Create visualization of points distribution
plt.figure(figsize=(15, 8))
plt.bar(df['Driver'][:10], df['Points'][:10])
plt.xticks(rotation=45, ha='right')
plt.title('2024 Saudi Arabian Grand Prix - Points Distribution (Top 10)')
plt.xlabel('Driver')
plt.ylabel('Points')
plt.tight_layout()
plt.savefig('/home/ubuntu/repos/Devin-Test/saudi_gp_2024_points.png')
plt.close()

# Additional Analysis and Visualizations

# 1. Team Performance Analysis
team_points = df.groupby('Team')['Points'].sum().sort_values(ascending=False)
plt.figure(figsize=(12, 6))
team_points.plot(kind='bar')
plt.title('2024 Saudi Arabian Grand Prix - Team Points')
plt.xlabel('Team')
plt.ylabel('Total Points')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('/home/ubuntu/repos/Devin-Test/saudi_gp_2024_team_points.png')
plt.close()

# 2. Gap to Winner Analysis (for top 10)
df['Gap_Seconds'] = df['Time/Gap'].apply(lambda x:
    float(x.replace('s', '')) if isinstance(x, str) and x.endswith('s')
    else 0 if x == '1:25:25.252'
    else None)

plt.figure(figsize=(12, 6))
gap_data = df[df['Gap_Seconds'].notna()].iloc[:10]
plt.bar(gap_data['Driver'], gap_data['Gap_Seconds'])
plt.title('Gap to Winner (Top 10 Finishers)')
plt.xlabel('Driver')
plt.ylabel('Gap to Winner (seconds)')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('/home/ubuntu/repos/Devin-Test/saudi_gp_2024_gaps.png')
plt.close()

# Detailed Statistics
print("\n2024 Saudi Arabian Grand Prix - Detailed Analysis")
print("-" * 50)
print("\nTeam Performance:")
print(team_points)

print("\nRace Statistics:")
print(f"Total Race Distance: {df['Laps'].max()} laps")
print(f"Drivers Finishing on Lead Lap: {len(df[df['Laps'] == df['Laps'].max()])} out of {len(df)}")
print(f"Average Points per Scoring Position: {df[df['Points'] > 0]['Points'].mean():.2f}")

# Team Battle Analysis
print("\nIntra-Team Battles (Position):")
for team in df['Team'].unique():
    team_drivers = df[df['Team'] == team].sort_values('Position')
    if len(team_drivers) == 2:
        driver1, driver2 = team_drivers.iloc[0], team_drivers.iloc[1]
        print(f"\n{team}:")
        print(f"{driver1['Driver']}: P{driver1['Position']} vs {driver2['Driver']}: P{driver2['Position']}")
