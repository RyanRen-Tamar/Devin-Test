"""
Mock data fetcher for testing ASIN sales processing pipeline.
Provides sample data in the same format as data_fetcher.py
"""
from datetime import datetime, date
from typing import Dict, List, Optional, Union

def fetch_sales_sc_data(asin_list: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    return [
        {
            'store_id': 'S001',
            'asin': 'B0BBGD3F1P',
            'purchase_cus_time': '2025-01-01',
            'item_price': 3000.0,
            'quantity': 150
        },
        {
            'store_id': 'S002',
            'asin': 'B0BDRYMTS4',
            'purchase_cus_time': '2025-01-01',
            'item_price': 1500.0,
            'quantity': 100
        }
    ]

def fetch_sales_vc_data(asin_list: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    return [
        {
            'store_id': 'S001',
            'asin': 'B0BBGD3F1P',
            'start_date': '2025-01-02',
            'ordered_revenue': 1387.5,
            'ordered_units': 75,
            'distributor_view': 'MANUFACTURING'
        }
    ]

def fetch_coupon_info(asin_list: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    return [
        {
            'store_id': 'S001',
            'asin': 'B0BBGD3F1P',
            'cus_date': '2025-01-01',
            'coupon_id': 'C001',
            'discount_type': 'Percentage',
            'discount_amount': 10
        },
        {
            'store_id': 'S002',
            'asin': 'B0BDRYMTS4',
            'cus_date': '2025-01-01',
            'coupon_id': 'C003',
            'discount_type': 'Fixed',
            'discount_amount': 5
        }
    ]

def fetch_deal_info(asin_list: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    return [
        {
            'store_id': 'DS001',
            'asin': 'B0BBGD3F1P',
            'cus_date': '2025-01-01',
            'deal_type': 'Flash Sale'
        },
        {
            'store_id': 'DS003',
            'asin': 'B0BDRYMTS4',
            'cus_date': '2025-01-01',
            'deal_type': 'Discount'
        }
    ]

def fetch_ad_data(asin_list: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    return [
        {
            'advertised_asin': 'B0BBGD3F1P',
            'cus_date': '2025-01-01',
            'spend': 200.0,
            'sales_7d': 5000.0,
            'units_sold_clicks_7d': 100
        },
        {
            'advertised_asin': 'B0BDRYMTS4',
            'cus_date': '2025-01-01',
            'spend': 150.0,
            'sales_7d': 3000.0,
            'units_sold_clicks_7d': 75
        },
        {
            'advertised_asin': 'B0BBGD3F1P',
            'cus_date': '2025-01-02',
            'spend': 50.0,
            'sales_7d': 1000.0,
            'units_sold_clicks_7d': 20
        }
    ]

def fetch_asin_hierarchy(asin_list: List[str]) -> Dict[str, List[str]]:
    return {
        'B0PARENT1': ['B0BBGD3F1P'],
        'B0PARENT2': ['B0BDRYMTS4']
    }

def fetch_orders_data(asin_list: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    return []  # Not used in current implementation

def fetch_campaign_report(asin_list: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    return []  # Not used in current implementation
