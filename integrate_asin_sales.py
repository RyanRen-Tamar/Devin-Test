"""
ASIN Sales Data Integration Pipeline

This script implements a data processing pipeline that:
1. Fetches and processes SC (Seller Central) and VC (Vendor Central) sales data
2. Integrates coupon and deal information
3. Aggregates data by ASIN and date
4. Adds advertising metrics
5. Optionally handles parent/child ASIN relationships

The pipeline follows the specifications detailed in the PRD document and uses
data fetching functions from data_fetcher.py.

Output: A comprehensive daily summary table containing:
- ASIN
- Date
- Last Price
- Sales Units
- Coupon Information
- Deal Information
- Advertising Metrics
"""

import pandas as pd
from typing import Dict, List, Optional, Set, Tuple, Union
from datetime import datetime, date


def process_sc_data(asin_list: List[str], 
                   start_date: Optional[str] = None, 
                   end_date: Optional[str] = None) -> pd.DataFrame:
    """
    Process Seller Central (SC) sales data according to PRD requirements.
    
    Args:
        asin_list: List of ASINs to fetch data for
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        DataFrame with columns:
        - store_id: Store identifier
        - ASIN: Product identifier
        - purchase_cus_time: Sales date (YYYY-MM-DD)
        - price: Daily price (item_price / quantity)
        - total_quantity: Daily total sales quantity
    """
    # Fetch raw SC data
    raw_data = fetch_sales_sc_data(asin_list, start_date, end_date)
    
    # Convert to DataFrame
    df = pd.DataFrame(raw_data)
    
    if df.empty:
        # Return empty DataFrame with correct columns if no data
        return pd.DataFrame(columns=['store_id', 'ASIN', 'purchase_cus_time', 
                                   'price', 'total_quantity'])
    
    # Convert purchase_cus_time to date only format (YYYY-MM-DD)
    df['purchase_cus_time'] = pd.to_datetime(df['purchase_cus_time']).dt.date
    
    # Calculate price (item_price / quantity)
    # Handle special cases:
    # 1. If quantity > 0 and item_price is NULL, set price to 0
    # 2. If quantity = 0, skip the record
    df = df[df['quantity'] != 0]  # Skip records where quantity = 0
    
    # Calculate price
    df['price'] = df.apply(
        lambda row: 0 if pd.isna(row['item_price']) and row['quantity'] > 0 
        else (row['item_price'] / row['quantity'] if row['quantity'] > 0 else 0), 
        axis=1
    )
    
    # Group by required fields and calculate total quantity
    result = df.groupby(
        ['store_id', 'asin', 'purchase_cus_time', 'price'],
        as_index=False
    ).agg({
        'quantity': 'sum'
    }).rename(columns={
        'quantity': 'total_quantity',
        'asin': 'ASIN'  # Standardize ASIN column name
    })
    
    return result


def process_vc_data(asin_list: List[str],
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> pd.DataFrame:
    """
    Process Vendor Central (VC) sales data according to PRD requirements.
    
    Args:
        asin_list: List of ASINs to fetch data for
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        DataFrame with columns:
        - store_id: Store identifier
        - ASIN: Product identifier
        - start_date: Sales date
        - price: Daily price (ordered_revenue / ordered_units)
        - total_ordered_units: Daily total ordered units
    """
    # Fetch raw VC data
    raw_data = fetch_sales_vc_data(asin_list, start_date, end_date)
    
    # Convert to DataFrame
    df = pd.DataFrame(raw_data)
    
    if df.empty:
        # Return empty DataFrame with correct columns if no data
        return pd.DataFrame(columns=['store_id', 'ASIN', 'start_date',
                                   'price', 'total_ordered_units'])
    
    # Calculate price (ordered_revenue / ordered_units)
    # Handle special case: if ordered_units is 0 or missing, set price to 0
    df['price'] = df.apply(
        lambda row: 0 if pd.isna(row['ordered_units']) or row['ordered_units'] == 0
        else (row['ordered_revenue'] / row['ordered_units']),
        axis=1
    )
    
    # For multiple records on same day, prioritize MANUFACTURING over SOURCING
    # First, sort by distributor_view to ensure MANUFACTURING comes first
    df['distributor_view_priority'] = df['distributor_view'].map(
        {'MANUFACTURING': 0, 'SOURCING': 1}
    )
    
    # Group by required fields, taking first price (after sorting by priority)
    # and sum ordered_units
    result = (df.sort_values('distributor_view_priority')
             .groupby(['store_id', 'asin', 'start_date'], as_index=False)
             .agg({
                 'price': 'first',
                 'ordered_units': 'sum'
             })
             .rename(columns={
                 'ordered_units': 'total_ordered_units',
                 'asin': 'ASIN'  # Standardize ASIN column name
             }))
    
    return result


def align_sc_vc_data(sc_df: pd.DataFrame, vc_df: pd.DataFrame) -> pd.DataFrame:
    """
    Align and merge SC and VC sales data into a unified format.
    
    Args:
        sc_df: Processed SC data with columns [store_id, ASIN, purchase_cus_time, price, total_quantity]
        vc_df: Processed VC data with columns [store_id, ASIN, start_date, price, total_ordered_units]
        
    Returns:
        DataFrame with unified columns:
        - store_id: Store identifier
        - ASIN: Product identifier
        - cus_date: Sales date
        - price: Daily price
        - sales_units: Daily sales quantity
    """
    # Rename VC columns to match target schema
    vc_aligned = vc_df.rename(columns={
        'start_date': 'cus_date',
        'total_ordered_units': 'sales_units'
    })
    
    # Rename SC columns to match target schema
    sc_aligned = sc_df.rename(columns={
        'purchase_cus_time': 'cus_date',
        'total_quantity': 'sales_units'
    })
    
    # Combine datasets
    combined_df = pd.concat([sc_aligned, vc_aligned], ignore_index=True)
    
    # Ensure all required columns exist
    required_columns = ['store_id', 'ASIN', 'cus_date', 'price', 'sales_units']
    for col in required_columns:
        if col not in combined_df.columns:
            combined_df[col] = 0
    
    # Fill missing values with 0
    combined_df[['price', 'sales_units']] = combined_df[['price', 'sales_units']].fillna(0)
    
    # Sort by date for convenience
    combined_df = combined_df.sort_values(['ASIN', 'cus_date', 'store_id'])
    
    return combined_df[required_columns]  # Ensure consistent column order


def transform_coupon_data(asin_list: List[str],
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> pd.DataFrame:
    """
    Transform coupon data according to PRD requirements.
    
    Args:
        asin_list: List of ASINs to fetch data for
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        DataFrame with columns:
        - store_id: Store identifier
        - ASIN: Product identifier
        - date: Coupon valid date
        - coupon: Combined discount info (e.g., "10+Percentage")
        - coupon_details: List of coupon IDs as string (e.g., "[C001, C002]")
    """
    import json
    from itertools import product
    
    # Fetch raw coupon data
    raw_data = fetch_coupon_info(asin_list, start_date, end_date)
    
    # Convert to DataFrame
    df = pd.DataFrame(raw_data)
    
    if df.empty:
        return pd.DataFrame(columns=['store_id', 'ASIN', 'date', 'coupon', 'coupon_details'])
    
    # Convert dates
    df['cus_date'] = pd.to_datetime(df['cus_date']).dt.date
    
    if df.empty:
        return pd.DataFrame(columns=['store_id', 'ASIN', 'date', 'coupon', 'coupon_details'])
    
    # Rename ASIN column to match convention
    df = df.rename(columns={'asin': 'ASIN'})
    
    # Create records with the current date
    records = []
    for _, row in df.iterrows():
        records.append({
            'store_id': row['store_id'],
            'ASIN': row['ASIN'],
            'date': row['cus_date'],
            'coupon': f"{row['discount_amount']}+{row['discount_type']}",
            'coupon_id': row['coupon_id']
        })
    
    # Convert records to DataFrame
    result_df = pd.DataFrame(records)
    
    # Group by store, ASIN, and date to combine multiple coupons
    result_df = (result_df.groupby(['store_id', 'ASIN', 'date'])
                .agg({
                    'coupon': 'first',  # Take the first coupon's discount info
                    'coupon_id': lambda x: f"[{', '.join(sorted(x))}]"  # Combine coupon IDs
                })
                .reset_index()
                .rename(columns={'coupon_id': 'coupon_details'}))
    
    return result_df


def merge_sales_with_coupon(sales_df: pd.DataFrame, coupon_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge sales data with coupon information.
    
    Args:
        sales_df: DataFrame with columns [store_id, ASIN, cus_date, price, sales_units]
        coupon_df: DataFrame with columns [store_id, ASIN, date, coupon, coupon_details]
        
    Returns:
        DataFrame with merged columns:
        - store_id: Store identifier
        - ASIN: Product identifier
        - cus_date: Sales date
        - price: Product price
        - sales_units: Number of units sold
        - coupon: Coupon discount info (NULL if no coupon)
        - coupon_details: List of coupon IDs (NULL if no coupon)
    """
    # Perform left merge to keep all sales records
    merged_df = pd.merge(
        sales_df,
        coupon_df,
        how='left',
        left_on=['store_id', 'ASIN', 'cus_date'],
        right_on=['store_id', 'ASIN', 'date']
    )
    
    # Drop redundant date column from coupon data
    if 'date' in merged_df.columns:
        merged_df = merged_df.drop(columns=['date'])
    
    # Ensure coupon fields are NULL (not empty string or 0) when no match
    merged_df['coupon'] = merged_df['coupon'].where(pd.notna(merged_df['coupon']), None)
    merged_df['coupon_details'] = merged_df['coupon_details'].where(pd.notna(merged_df['coupon_details']), None)
    
    # Sort by date and ASIN for convenience
    merged_df = merged_df.sort_values(['cus_date', 'ASIN', 'store_id'])
    
    # Ensure consistent column order
    columns = ['store_id', 'ASIN', 'cus_date', 'price', 'sales_units', 'coupon', 'coupon_details']
    return merged_df[columns]


def transform_deal_data(asin_list: List[str],
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> pd.DataFrame:
    """
    Transform deal data according to PRD requirements.
    
    Args:
        asin_list: List of ASINs to fetch data for
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        DataFrame with columns:
        - store_id: Store identifier
        - ASIN: Product identifier
        - date: Deal valid date
        - type: Deal type
        - deal_store_id: Store ID associated with the deal
    """
    import json
    
    # Fetch raw deal data
    raw_data = fetch_deal_info(asin_list, start_date, end_date)
    
    # Convert to DataFrame
    df = pd.DataFrame(raw_data)
    
    # For mock data, we assume all deals are valid
    if df.empty:
        return pd.DataFrame(columns=['store_id', 'ASIN', 'date', 'type', 'deal_store_id'])
    
    # Convert dates
    df['cus_date'] = pd.to_datetime(df['cus_date']).dt.date
    
    # Rename ASIN column to match convention
    df = df.rename(columns={'asin': 'ASIN'})
    
    # Create records with the current date
    records = []
    for _, row in df.iterrows():
        records.append({
            'store_id': row['store_id'],
            'ASIN': row['ASIN'],
            'date': row['cus_date'],
            'type': row['deal_type'],  # Using deal_type from mock data
            'deal_store_id': row['store_id']  # Same as store_id per example
        })
    
    # Convert records to DataFrame
    result_df = pd.DataFrame(records)
    
    # Sort by date and ASIN for convenience
    result_df = result_df.sort_values(['date', 'ASIN', 'store_id'])
    
    return result_df


def merge_sales_with_deal(sales_df: pd.DataFrame, deal_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge sales data (with coupon info) with deal information.
    
    Args:
        sales_df: DataFrame with columns [store_id, ASIN, cus_date, price, sales_units, coupon, coupon_details]
        deal_df: DataFrame with columns [store_id, ASIN, date, type, deal_store_id]
        
    Returns:
        DataFrame with merged columns:
        - store_id: Store identifier
        - ASIN: Product identifier
        - cus_date: Sales date
        - price: Product price
        - sales_units: Number of units sold
        - coupon: Coupon discount info (NULL if no coupon)
        - coupon_details: List of coupon IDs (NULL if no coupon)
        - type: Deal type (NULL if no deal)
        - deal_store_id: Store ID of the deal (NULL if no deal)
    """
    # Perform left merge to keep all sales records
    merged_df = pd.merge(
        sales_df,
        deal_df,
        how='left',
        left_on=['store_id', 'ASIN', 'cus_date'],
        right_on=['store_id', 'ASIN', 'date']
    )
    
    # Drop redundant date column from deal data
    if 'date' in merged_df.columns:
        merged_df = merged_df.drop(columns=['date'])
    
    # Ensure deal fields are NULL (not empty string or 0) when no match
    merged_df['type'] = merged_df['type'].where(pd.notna(merged_df['type']), None)
    merged_df['deal_store_id'] = merged_df['deal_store_id'].where(pd.notna(merged_df['deal_store_id']), None)
    
    # Sort by date and ASIN for convenience
    merged_df = merged_df.sort_values(['cus_date', 'ASIN', 'store_id'])
    
    # Ensure consistent column order
    columns = ['store_id', 'ASIN', 'cus_date', 'price', 'sales_units',
              'coupon', 'coupon_details', 'type', 'deal_store_id']
    return merged_df[columns]


def aggregate_sales_data(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate sales data by ASIN and date, combining coupon and deal information.
    
    Args:
        sales_df: DataFrame with columns [store_id, ASIN, cus_date, price, sales_units,
                                        coupon, coupon_details, type, deal_store_id]
        
    Returns:
        DataFrame with aggregated columns:
        - ASIN: Product identifier
        - cus_date: Sales date
        - last_price: Price from record with highest sales volume
        - sales_units: Total sales quantity
        - coupon: Selected coupon discount info
        - coupon_details: Combined list of coupon IDs
        - deal: Combined list of deal types
        - deal_store_id: Combined list of deal store IDs
    """
    # Group by ASIN and date to calculate aggregates
    grouped = sales_df.groupby(['ASIN', 'cus_date'])
    
    # Calculate total sales units for each group
    sales_agg = grouped.agg({
        'sales_units': 'sum'
    }).reset_index()
    
    # For each group, get the price from the record with highest sales
    price_data = []
    for (asin, date), group in grouped:
        # Get record with highest sales
        max_sales_record = group.loc[group['sales_units'].idxmax()]
        price_data.append({
            'ASIN': asin,
            'cus_date': date,
            'last_price': max_sales_record['price']
        })
    price_df = pd.DataFrame(price_data)
    
    # Merge price data with sales aggregates
    result = pd.merge(
        sales_agg,
        price_df,
        on=['ASIN', 'cus_date']
    )
    
    # Process coupons according to rules
    coupon_data = []
    for (asin, date), group in grouped:
        # Filter out records without coupons
        coupons = group[group['coupon'].notna()]
        if not coupons.empty:
            # Parse discount type and amount
            coupon_info = coupons['coupon'].str.split('+', expand=True)
            coupon_info.columns = ['amount', 'type']
            coupon_info['amount'] = pd.to_numeric(coupon_info['amount'])
            
            # Select coupon based on rules:
            # - If same type, take highest amount
            # - If different types, take random one
            if len(set(coupon_info['type'])) == 1:
                # Same type - take highest amount
                max_amount_idx = coupon_info['amount'].idxmax()
                selected_coupon = coupons.iloc[coupons.index.get_loc(max_amount_idx)]
            else:
                # Different types - take random one
                selected_coupon = coupons.sample(n=1).iloc[0]
            
            # Combine all coupon IDs
            all_coupon_ids = []
            for details in coupons['coupon_details'].dropna():
                # Remove brackets and split
                ids = details.strip('[]').split(', ')
                all_coupon_ids.extend(ids)
            
            coupon_data.append({
                'ASIN': asin,
                'cus_date': date,
                'coupon': selected_coupon['coupon'],
                'coupon_details': f"[{', '.join(sorted(set(all_coupon_ids)))}]"
            })
    
    # Convert coupon data to DataFrame and merge
    if coupon_data:
        coupon_df = pd.DataFrame(coupon_data)
        result = pd.merge(result, coupon_df, on=['ASIN', 'cus_date'], how='left')
    else:
        result['coupon'] = None
        result['coupon_details'] = None
    
    # Process deals - combine all types and store IDs into lists
    deal_data = []
    for (asin, date), group in grouped:
        # Filter out records without deals
        deals = group[group['type'].notna()]
        if not deals.empty:
            deal_types = sorted(set(deals['type'].dropna()))
            deal_stores = sorted(set(deals['deal_store_id'].dropna()))
            
            deal_data.append({
                'ASIN': asin,
                'cus_date': date,
                'deal': f"[{', '.join(deal_types)}]",
                'deal_store_id': f"[{', '.join(deal_stores)}]"
            })
    
    # Convert deal data to DataFrame and merge
    if deal_data:
        deal_df = pd.DataFrame(deal_data)
        result = pd.merge(result, deal_df, on=['ASIN', 'cus_date'], how='left')
    else:
        result['deal'] = None
        result['deal_store_id'] = None
    
    # Sort by date and ASIN
    result = result.sort_values(['cus_date', 'ASIN'])
    
    # Ensure consistent column order
    columns = ['ASIN', 'cus_date', 'last_price', 'sales_units',
              'coupon', 'coupon_details', 'deal', 'deal_store_id']
    return result[columns]


def fetch_and_aggregate_ad_data(asin_list: List[str],
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch and aggregate advertising data by ASIN and date.
    
    Args:
        asin_list: List of ASINs to fetch data for
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        DataFrame with columns:
        - ASIN: Product identifier
        - cus_date: Ad date
        - ad_cost: Total ad spend
        - ad_sales: Total 7-day attributed sales
        - ad_units_sold: Total 7-day attributed units sold
    """
    # Fetch raw ad data
    raw_data = fetch_ad_data(asin_list, start_date, end_date)
    
    # Convert to DataFrame
    df = pd.DataFrame(raw_data)
    
    if df.empty:
        return pd.DataFrame(columns=['ASIN', 'cus_date', 'ad_cost', 'ad_sales', 'ad_units_sold'])
    
    # Rename columns to match requirements
    df = df.rename(columns={
        'advertised_asin': 'ASIN',
        'spend': 'ad_cost',
        'sales_7d': 'ad_sales',
        'units_sold_clicks_7d': 'ad_units_sold'
    })
    
    # Group by ASIN and date to calculate aggregates
    result = df.groupby(['ASIN', 'cus_date']).agg({
        'ad_cost': 'sum',
        'ad_sales': 'sum',
        'ad_units_sold': 'sum'
    }).reset_index()
    
    # Fill NULL values with 0
    result = result.fillna(0)
    
    # Sort by date and ASIN
    result = result.sort_values(['cus_date', 'ASIN'])
    
    return result


def check_pasin_needed(asin_list: List[str]) -> bool:
    """
    Check if parent ASIN processing is needed by examining if any ASINs
    in the input list are parent ASINs that need to be mapped to child ASINs.
    
    Args:
        asin_list: List of ASINs to check
        
    Returns:
        bool: True if any ASIN in the list is a parent ASIN, False otherwise
    """
    # Fetch ASIN hierarchy data
    hierarchy_data = fetch_asin_hierarchy(asin_list)
    
    # If hierarchy_data is empty, no parent ASINs exist
    if not hierarchy_data:
        return False
    
    # Check if any ASIN in the input list is a parent ASIN
    # hierarchy_data is a dict where keys are parent ASINs
    parent_asins = set(hierarchy_data.keys())
    input_asins = set(asin_list)
    
    # Return True if there's any overlap between parent ASINs and input ASINs
    return bool(parent_asins & input_asins)


def identify_and_assign_parent_asin(df: pd.DataFrame, asin_list: List[str]) -> pd.DataFrame:
    """
    Add parent ASIN information to the DataFrame if parent ASINs exist.
    
    Args:
        df: DataFrame with ASIN column
        asin_list: List of ASINs to check for parent-child relationships
        
    Returns:
        DataFrame with additional parent_asin column if parent ASINs exist
    """
    # Fetch ASIN hierarchy data
    hierarchy_data = fetch_asin_hierarchy(asin_list)
    
    # Create parent-child mapping
    parent_child_map = {}
    for parent_asin, child_asins in hierarchy_data.items():
        for child_asin in child_asins:
            parent_child_map[child_asin] = parent_asin
    
    # Add parent_asin column, defaulting to NULL for ASINs without parents
    df['parent_asin'] = df['ASIN'].map(parent_child_map)
    
    return df


def process_asin_sales(asin_list: List[str],
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> pd.DataFrame:
    """
    Main function to process ASIN sales data and generate the final summary table.
    
    Args:
        asin_list: List of ASINs to process
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        DataFrame with all required metrics:
        - ASIN: Product identifier
        - cus_date: Sales date
        - last_price: Price from highest sales volume
        - sales_units: Total sales quantity
        - coupon: Selected coupon discount info
        - coupon_details: Combined coupon IDs
        - deal: Combined deal types
        - deal_store_id: Combined deal store IDs
        - ad_cost: Total ad spend
        - ad_sales: Total 7-day attributed sales
        - ad_units_sold: Total 7-day attributed units
        - parent_asin: Parent ASIN (if applicable)
    """
    # Process SC sales data
    sc_data = process_sc_data(asin_list, start_date, end_date)
    
    # Process VC sales data
    vc_data = process_vc_data(asin_list, start_date, end_date)
    
    # Align SC and VC data
    sales_data = align_sc_vc_data(sc_data, vc_data)
    
    # Process coupon data
    coupon_data = transform_coupon_data(asin_list, start_date, end_date)
    
    # Merge sales with coupon data
    sales_with_coupon = merge_sales_with_coupon(sales_data, coupon_data)
    
    # Process deal data
    deal_data = transform_deal_data(asin_list, start_date, end_date)
    
    # Merge sales with deal data
    sales_with_deals = merge_sales_with_deal(sales_with_coupon, deal_data)
    
    # Aggregate sales data
    aggregated_sales = aggregate_sales_data(sales_with_deals)
    
    # Fetch and aggregate ad data
    ad_data = fetch_and_aggregate_ad_data(asin_list, start_date, end_date)
    
    # Merge with ad data
    result = pd.merge(
        aggregated_sales,
        ad_data,
        on=['ASIN', 'cus_date'],
        how='left'
    )
    
    # Fill missing ad data with 0
    ad_columns = ['ad_cost', 'ad_sales', 'ad_units_sold']
    result[ad_columns] = result[ad_columns].fillna(0)
    
    # Always process parent ASINs (will be NULL if no parent exists)
    result = identify_and_assign_parent_asin(result, asin_list)
    
    # Sort by date and ASIN
    result = result.sort_values(['cus_date', 'ASIN'])
    
    return result


def verify_sample_data():
    """
    Verify the ASIN sales processing pipeline using sample data.
    Tests various scenarios and data combinations to ensure correct output.
    """
    # Test case 1: Basic functionality with sample ASINs
    sample_asins = ['B0BBGD3F1P', 'B0BDRYMTS4']
    start_date = '2025-01-01'
    end_date = '2025-01-02'
    
    result = process_asin_sales(sample_asins, start_date, end_date)
    
    # Verify DataFrame structure
    required_columns = {
        'ASIN', 'cus_date', 'last_price', 'sales_units',
        'coupon', 'coupon_details', 'deal', 'deal_store_id',
        'ad_cost', 'ad_sales', 'ad_units_sold', 'parent_asin'
    }
    
    missing_columns = required_columns - set(result.columns)
    if missing_columns:
        print(f"ERROR: Missing required columns: {missing_columns}")
        return False
    
    # Verify data types
    if not (
        result['ASIN'].dtype == 'object' and  # string
        isinstance(result['cus_date'].iloc[0], date) and  # date object
        pd.api.types.is_numeric_dtype(result['last_price']) and
        pd.api.types.is_numeric_dtype(result['sales_units']) and
        pd.api.types.is_numeric_dtype(result['ad_cost']) and
        pd.api.types.is_numeric_dtype(result['ad_sales']) and
        pd.api.types.is_numeric_dtype(result['ad_units_sold'])
    ):
        print("ERROR: Incorrect data types in output")
        return False
    
    # Verify NULL handling
    if not (
        result['coupon'].isna().any() and  # Should have some NULL values
        result['deal'].isna().any() and    # Should have some NULL values
        (result['ad_cost'] >= 0).all() and  # Ad metrics should be >= 0
        (result['ad_sales'] >= 0).all() and
        (result['ad_units_sold'] >= 0).all()
    ):
        print("ERROR: Incorrect NULL handling or negative ad metrics")
        return False
    
    # Verify sorting
    if not result.equals(result.sort_values(['cus_date', 'ASIN'])):
        print("ERROR: Output is not properly sorted by date and ASIN")
        return False
    
    # Verify list format for coupon_details and deal columns
    list_columns = ['coupon_details', 'deal', 'deal_store_id']
    for col in list_columns:
        non_null_values = result[col].dropna()
        if not non_null_values.empty and not all(
            str(val).startswith('[') and str(val).endswith(']')
            for val in non_null_values
        ):
            print(f"ERROR: {col} values not in correct list format")
            return False
    
    print("All verification checks passed successfully!")
    print("\nSample output:")
    print(result.head().to_string())
    return True


if __name__ == '__main__':
    verify_sample_data()


# Import mock data fetching functions for testing
from mock_data_fetcher import (
    fetch_asin_hierarchy,
    fetch_coupon_info,
    fetch_deal_info,
    fetch_sales_sc_data,
    fetch_sales_vc_data,
    fetch_ad_data,
    fetch_orders_data,
    fetch_campaign_report
)
