import json
import pandas as pd
from datetime import datetime
# Remove matplotlib and seaborn imports as they're no longer needed

# Test data structure
test_data = {
  "ad_performance": [
    {
      "campaign_id": "CAM_A001",
      "campaign_name": "SummerSale",
      "date": "2025-05-01",
      "spend": 80.5,
      "impressions": 15000,
      "clicks": 520,
      "ad_sales": 250.0,
      "units_sold": 15,
      "cpc": 0.28,
      "roi": 2.10, 
      "acos": 32.2,
      "daily_spend_ratio": 0.80, 
      "weekly_spend_ratio": 0.35,
      "tacos": 6.5,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_A001",
      "campaign_name": "SummerSale",
      "date": "2025-05-02",
      "spend": 90.0,
      "impressions": 16500,
      "clicks": 600,
      "ad_sales": 270.0,
      "units_sold": 16,
      "cpc": 0.30,
      "roi": 2.00,
      "acos": 33.3,
      "daily_spend_ratio": 0.90,
      "weekly_spend_ratio": 0.40,
      "tacos": 7.5,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_A001",
      "campaign_name": "SummerSale",
      "date": "2025-05-03",
      "spend": None,
      "impressions": 14000,
      "clicks": 550,
      "ad_sales": 260.0,
      "units_sold": 15,
      "cpc": 0.32,
      "roi": None,
      "acos": None,
      "daily_spend_ratio": None,
      "weekly_spend_ratio": 0.45,
      "tacos": None,
      "missing_data_flag": True,
      "notes": "原始數據缺失，無法計算花費"
    },
    {
      "campaign_id": "CAM_A001",
      "campaign_name": "SummerSale",
      "date": "2025-05-04",
      "spend": 75.5,
      "impressions": 13000,
      "clicks": 490,
      "ad_sales": 220.0,
      "units_sold": 13,
      "cpc": 0.27,
      "roi": 1.91,
      "acos": 34.3,
      "daily_spend_ratio": 0.75,
      "weekly_spend_ratio": 0.48,
      "tacos": 8.0,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_A001",
      "campaign_name": "SummerSale",
      "date": "2025-05-05",
      "spend": 105.0,
      "impressions": 18000,
      "clicks": 680,
      "ad_sales": 310.0,
      "units_sold": 19,
      "cpc": 0.32,
      "roi": 1.95,
      "acos": 33.9,
      "daily_spend_ratio": 1.05,
      "weekly_spend_ratio": 0.53,
      "tacos": 9.0,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_A001",
      "campaign_name": "SummerSale",
      "date": "2025-05-06",
      "spend": 98.0,
      "impressions": 15500,
      "clicks": 610,
      "ad_sales": 280.0,
      "units_sold": 17,
      "cpc": 0.30,
      "roi": 1.86,
      "acos": 35.0,
      "daily_spend_ratio": 0.98,
      "weekly_spend_ratio": 0.58,
      "tacos": 8.2,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_A001",
      "campaign_name": "SummerSale",
      "date": "2025-05-07",
      "spend": 110.0,
      "impressions": 20000,
      "clicks": 720,
      "ad_sales": 330.0,
      "units_sold": 20,
      "cpc": 0.31,
      "roi": 2.00,
      "acos": 33.3,
      "daily_spend_ratio": 1.10,
      "weekly_spend_ratio": 0.64,
      "tacos": 9.5,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_B002",
      "campaign_name": "MegaDeal",
      "date": "2025-05-01",
      "spend": 45.0,
      "impressions": 10000,
      "clicks": 300,
      "ad_sales": 150.0,
      "units_sold": 10,
      "cpc": 0.15,
      "roi": 2.33,
      "acos": 30.0,
      "daily_spend_ratio": 0.45,
      "weekly_spend_ratio": 0.20,
      "tacos": 5.5,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_B002",
      "campaign_name": "MegaDeal",
      "date": "2025-05-02",
      "spend": 50.0,
      "impressions": 12000,
      "clicks": 360,
      "ad_sales": 180.0,
      "units_sold": 11,
      "cpc": 0.14,
      "roi": 2.60,
      "acos": 27.8,
      "daily_spend_ratio": 0.50,
      "weekly_spend_ratio": 0.25,
      "tacos": 5.0,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_B002",
      "campaign_name": "MegaDeal",
      "date": "2025-05-03",
      "spend": 60.0,
      "impressions": 11000,
      "clicks": 340,
      "ad_sales": 160.0,
      "units_sold": 9,
      "cpc": 0.18,
      "roi": 1.67,
      "acos": 37.5,
      "daily_spend_ratio": 0.60,
      "weekly_spend_ratio": 0.30,
      "tacos": 6.2,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_B002",
      "campaign_name": "MegaDeal",
      "date": "2025-05-04",
      "spend": 55.0,
      "impressions": 10500,
      "clicks": 330,
      "ad_sales": 155.0,
      "units_sold": 10,
      "cpc": 0.17,
      "roi": 1.82,
      "acos": 35.5,
      "daily_spend_ratio": 0.55,
      "weekly_spend_ratio": 0.33,
      "tacos": 5.9,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_B002",
      "campaign_name": "MegaDeal",
      "date": "2025-05-05",
      "spend": 40.0,
      "impressions": 8500,
      "clicks": 280,
      "ad_sales": 120.0,
      "units_sold": 7,
      "cpc": 0.14,
      "roi": 2.00,
      "acos": 33.3,
      "daily_spend_ratio": 0.40,
      "weekly_spend_ratio": 0.37,
      "tacos": 4.8,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_B002",
      "campaign_name": "MegaDeal",
      "date": "2025-05-06",
      "spend": 75.0,
      "impressions": 16000,
      "clicks": 450,
      "ad_sales": 210.0,
      "units_sold": 14,
      "cpc": 0.17,
      "roi": 1.80,
      "acos": 35.7,
      "daily_spend_ratio": 0.75,
      "weekly_spend_ratio": 0.42,
      "tacos": 6.0,
      "missing_data_flag": False,
      "notes": ""
    },
    {
      "campaign_id": "CAM_B002",
      "campaign_name": "MegaDeal",
      "date": "2025-05-07",
      "spend": 85.0,
      "impressions": 19000,
      "clicks": 520,
      "ad_sales": 270.0,
      "units_sold": 18,
      "cpc": 0.16,
      "roi": 2.18,
      "acos": 31.5,
      "daily_spend_ratio": 0.85,
      "weekly_spend_ratio": 0.48,
      "tacos": 7.2,
      "missing_data_flag": False,
      "notes": ""
    }
  ],
  "listing_info": [
    {
      "asin": "B07ABC1234",
      "sku": "SKU-SUMMER-L",
      "current_price": 24.99,
      "stock_quantity": 320,
      "coupon_active": True,
      "deal_active": False,
      "estimated_daily_sales": 14
    },
    {
      "asin": "B07XYZ5678",
      "sku": "SKU-MEGA-XL",
      "current_price": 19.99,
      "stock_quantity": 150,
      "coupon_active": False,
      "deal_active": True,
      "estimated_daily_sales": 10
    }
  ],
  "budget_config": [
    {
      "campaign_id": "CAM_A001",
      "budget_id": "BUDGET_A",
      "budget_type": "daily",
      "budget_amount": 100.0,
      "threshold_percentage_high": 0.9,
      "threshold_percentage_low": 0.4
    },
    {
      "campaign_id": "CAM_A001",
      "budget_id": "BUDGET_A_WEEK",
      "budget_type": "weekly",
      "budget_amount": 700.0,
      "threshold_percentage_high": 0.9,
      "threshold_percentage_low": 0.5
    },
    {
      "campaign_id": "CAM_B002",
      "budget_id": "BUDGET_B",
      "budget_type": "daily",
      "budget_amount": 100.0,
      "threshold_percentage_high": 0.9,
      "threshold_percentage_low": 0.3
    },
    {
      "campaign_id": "CAM_B002",
      "budget_id": "BUDGET_B_WEEK",
      "budget_type": "weekly",
      "budget_amount": 700.0,
      "threshold_percentage_high": 0.85,
      "threshold_percentage_low": 0.4
    }
  ]
}

# Create DataFrames
ad_performance_df = pd.DataFrame(test_data["ad_performance"])
listing_info_df = pd.DataFrame(test_data["listing_info"])
budget_config_df = pd.DataFrame(test_data["budget_config"])

# Display basic information about each dataset
print("\nAd Performance Data Structure:")
print(ad_performance_df.info())
print("\nSample of Ad Performance Data:")
print(ad_performance_df.head())

print("\nListing Info Data Structure:")
print(listing_info_df.info())
print("\nSample of Listing Info Data:")
print(listing_info_df)

print("\nBudget Config Data Structure:")
print(budget_config_df.info())
print("\nSample of Budget Config Data:")
print(budget_config_df)

# Convert date column to datetime
ad_performance_df['date'] = pd.to_datetime(ad_performance_df['date'])

# Data completeness check
print("\n数据完整性检查:")
missing_data = {
    'spend': ad_performance_df[ad_performance_df['spend'].isnull()],
    'roi': ad_performance_df[ad_performance_df['roi'].isnull()],
    'acos': ad_performance_df[ad_performance_df['acos'].isnull()],
    'tacos': ad_performance_df[ad_performance_df['tacos'].isnull()]
}

for metric, missing_entries in missing_data.items():
    if not missing_entries.empty:
        print(f"\n{metric.upper()} 数据缺失情况:")
        print(missing_entries[['campaign_name', 'date', 'notes']])
        
# Calculate campaign-level metrics
campaign_metrics = ad_performance_df.groupby('campaign_name').agg({
    'spend': ['sum', 'mean', 'std'],
    'impressions': ['sum', 'mean'],
    'clicks': ['sum', 'mean'],
    'ad_sales': ['sum', 'mean'],
    'units_sold': ['sum', 'mean'],
    'roi': 'mean',
    'acos': 'mean',
    'tacos': 'mean'
}).round(2)

print("\nCampaign Level Metrics:")
print(campaign_metrics)

# Analyze budget utilization
budget_analysis = pd.merge(
    ad_performance_df, 
    budget_config_df[budget_config_df['budget_type'] == 'daily'],
    on='campaign_id'
)

print("\nBudget Utilization Analysis:")
budget_summary = budget_analysis.groupby('campaign_name').agg({
    'spend': 'sum',
    'budget_amount': 'first',
    'daily_spend_ratio': ['mean', 'max', 'min']
}).round(2)
print(budget_summary)

# Generate ECharts visualizations
from scripts.generate_charts_echarts import generate_daily_spend_ratio_echarts, generate_spend_vs_sales_echarts

# Generate and save ECharts configurations
spend_ratio_config = generate_daily_spend_ratio_echarts(ad_performance_df)
spend_sales_config = generate_spend_vs_sales_echarts(ad_performance_df)

# Save ECharts configurations to JSON files
with open('/home/ubuntu/repos/Devin-Test/spend_ratio_echarts.json', 'w', encoding='utf-8') as f:
    f.write(spend_ratio_config)
    
with open('/home/ubuntu/repos/Devin-Test/spend_sales_echarts.json', 'w', encoding='utf-8') as f:
    f.write(spend_sales_config)

# Save processed data for reporting
campaign_metrics.to_csv('/home/ubuntu/repos/Devin-Test/campaign_metrics.csv')
budget_summary.to_csv('/home/ubuntu/repos/Devin-Test/budget_summary.csv')
