import os
import re
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from data_fetcher import (
    fetch_sales_vc_data,
    fetch_sales_sc_data,
    fetch_coupon_info,
    fetch_deal_info
)
from data_feasibility import check_data_feasibility

logger = logging.getLogger(__name__)

def validate_output(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validate the output DataFrame using data_feasibility checks.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        (bool, str): Tuple of (is_valid, reason)
    """
    if df.empty:
        return False, "EMPTY_DATAFRAME"
        
    # Convert DataFrame to list of dicts for validation
    records = df.to_dict('records')
    
    # Define required fields based on output schema
    required_fields = [
        'asin', 'date', 'price', 'price_store_id', 'volume',
        'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
    ]
    
    # Validate using existing feasibility checker
    return check_data_feasibility(
        records=records,
        min_days=5,  # Minimum 5 days of data
        required_fields=required_fields,
        date_field='date',
        missing_threshold=0.5,  # Allow up to 50% missing data
        max_gap_days=7  # Maximum 7 days gap in data
    )

def vc_sale_coupon_deal(
    asin_list: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Process VC (Vendor Central) sales data with coupon and deal information.

    Args:
        asin_list: List of ASINs to process
        start_date: Start date for data range (YYYY-MM-DD)
        end_date: End date for data range (YYYY-MM-DD)

    Returns:
        DataFrame with columns:
        - asin: Product ASIN
        - date: Date of sale
        - price: Unit price
        - price_store_id: Store ID for the price
        - volume: Sales volume
        - coupon: Main coupon info
        - coupon_details: Detailed coupon information
        - coupon_count: Number of coupons
        - deal: Deal information
        - deal_store_id: Store ID for the deal
    """
    # Fetch VC sales data
    vc_data = fetch_sales_vc_data(asin_list, start_date, end_date)
    if not vc_data:
        logger.warning("No VC data found for the given parameters")
        return pd.DataFrame(columns=[
            'asin', 'date', 'price', 'price_store_id', 'volume',
            'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
        ])

    # Convert to DataFrame and compute unit price
    df_vc = pd.DataFrame(vc_data)
    df_vc['price'] = df_vc.apply(
        lambda row: row['ordered_revenue'] / row['ordered_units'] 
        if row['ordered_units'] != 0 else 0,
        axis=1
    )

    # Fetch coupon data for the same period
    coupon_data = fetch_coupon_info(asin_list, start_date, end_date)
    df_coupon = pd.DataFrame(coupon_data) if coupon_data else pd.DataFrame()

    # Fetch deal data for the same period
    deal_data = fetch_deal_info(asin_list, start_date, end_date)
    df_deal = pd.DataFrame(deal_data) if deal_data else pd.DataFrame()

    # Process coupon information
    if not df_coupon.empty:
        # Group coupons by date and ASIN
        coupon_groups = df_coupon.groupby(['start_cus_dt', 'asins']).agg({
            'discount_amount': 'max',
            'discount_type': lambda x: x.iloc[0],  # Take first discount type if multiple
            'name': lambda x: ', '.join(set(x))  # Combine coupon names
        }).reset_index()
        
        # Format coupon info
        coupon_groups['coupon'] = coupon_groups.apply(
            lambda row: f"{row['discount_amount']}{row['discount_type']}", 
            axis=1
        )
    else:
        coupon_groups = pd.DataFrame(columns=['start_cus_dt', 'asins', 'coupon', 'name'])

    # Process deal information
    if not df_deal.empty:
        # Group deals by date and ASIN
        deal_groups = df_deal.groupby(['start_cus_dt', 'included_products']).agg({
            'type': 'first',
            'store_id': 'first'
        }).reset_index()
    else:
        deal_groups = pd.DataFrame(columns=['start_cus_dt', 'included_products', 'type', 'store_id'])

    # Prepare final DataFrame
    result = pd.DataFrame({
        'asin': df_vc['asin'],
        'date': df_vc['start_date'],
        'price': df_vc['price'],
        'price_store_id': df_vc['store_id'],
        'volume': df_vc['ordered_units']
    })

    # Add coupon information
    result['coupon'] = ''
    result['coupon_details'] = ''
    result['coupon_count'] = 0
    if not coupon_groups.empty:
        for idx, row in result.iterrows():
            matching_coupons = coupon_groups[
                (coupon_groups['start_cus_dt'] == row['date']) & 
                (coupon_groups['asins'].str.contains(row['asin'], na=False))
            ]
            if not matching_coupons.empty:
                result.at[idx, 'coupon'] = matching_coupons['coupon'].iloc[0]
                result.at[idx, 'coupon_details'] = matching_coupons['name'].iloc[0]
                result.at[idx, 'coupon_count'] = len(matching_coupons)

    # Add deal information
    result['deal'] = ''
    result['deal_store_id'] = ''
    if not deal_groups.empty:
        for idx, row in result.iterrows():
            matching_deals = deal_groups[
                (deal_groups['start_cus_dt'] == row['date']) & 
                (deal_groups['included_products'].str.contains(row['asin'], na=False))
            ]
            if not matching_deals.empty:
                result.at[idx, 'deal'] = matching_deals['type'].iloc[0]
                result.at[idx, 'deal_store_id'] = matching_deals['store_id'].iloc[0]

    return result

def sc_sale_coupon_deal(
    asin_list: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Process SC (Sales Central) sales data with coupon and deal information.

    Args:
        asin_list: List of ASINs to process
        start_date: Start date for data range (YYYY-MM-DD)
        end_date: End date for data range (YYYY-MM-DD)

    Returns:
        DataFrame with columns:
        - asin: Product ASIN
        - date: Date of sale
        - price: Unit price
        - price_store_id: Store ID for the price
        - volume: Sales volume
        - coupon: Main coupon info
        - coupon_details: Detailed coupon information
        - coupon_count: Number of coupons
        - deal: Deal information
        - deal_store_id: Store ID for the deal
    """
    # Fetch SC sales data
    sc_data = fetch_sales_sc_data(asin_list, start_date, end_date)
    if not sc_data:
        logger.warning("No SC data found for the given parameters")
        return pd.DataFrame(columns=[
            'asin', 'date', 'price', 'price_store_id', 'volume',
            'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
        ])

    # Convert to DataFrame
    df_sc = pd.DataFrame(sc_data)
    
    # Calculate unit price from sales amount and quantity
    df_sc['price'] = df_sc.apply(
        lambda row: row['ordered_product_sales_amount'] / row['units_ordered']
        if row['units_ordered'] != 0 else 0,
        axis=1
    )
    
    # Fetch coupon data for the same period
    coupon_data = fetch_coupon_info(asin_list, start_date, end_date)
    df_coupon = pd.DataFrame(coupon_data) if coupon_data else pd.DataFrame()

    # Fetch deal data for the same period
    deal_data = fetch_deal_info(asin_list, start_date, end_date)
    df_deal = pd.DataFrame(deal_data) if deal_data else pd.DataFrame()

    # Process coupon information
    if not df_coupon.empty:
        # Group coupons by date and ASIN
        coupon_groups = df_coupon.groupby(['start_cus_dt', 'asins']).agg({
            'discount_amount': 'max',
            'discount_type': lambda x: x.iloc[0],  # Take first discount type if multiple
            'name': lambda x: ', '.join(set(x))  # Combine coupon names
        }).reset_index()
        
        # Format coupon info
        coupon_groups['coupon'] = coupon_groups.apply(
            lambda row: f"{row['discount_amount']}{row['discount_type']}", 
            axis=1
        )
    else:
        coupon_groups = pd.DataFrame(columns=['start_cus_dt', 'asins', 'coupon', 'name'])

    # Process deal information
    if not df_deal.empty:
        # Group deals by date and ASIN
        deal_groups = df_deal.groupby(['start_cus_dt', 'included_products']).agg({
            'type': 'first',
            'store_id': 'first'
        }).reset_index()
    else:
        deal_groups = pd.DataFrame(columns=['start_cus_dt', 'included_products', 'type', 'store_id'])

    # Prepare final DataFrame
    result = pd.DataFrame({
        'asin': df_sc['asin'],
        'date': df_sc['cus_date'],
        'price': df_sc['price'],  # Use calculated unit price
        'price_store_id': df_sc['store_id'],
        'volume': df_sc['units_ordered']
    })

    # Add coupon information
    result['coupon'] = ''
    result['coupon_details'] = ''
    result['coupon_count'] = 0
    if not coupon_groups.empty:
        for idx, row in result.iterrows():
            matching_coupons = coupon_groups[
                (coupon_groups['start_cus_dt'] == row['date']) & 
                (coupon_groups['asins'].str.contains(row['asin'], na=False))
            ]
            if not matching_coupons.empty:
                result.at[idx, 'coupon'] = matching_coupons['coupon'].iloc[0]
                result.at[idx, 'coupon_details'] = matching_coupons['name'].iloc[0]
                result.at[idx, 'coupon_count'] = len(matching_coupons)

    # Add deal information
    result['deal'] = ''
    result['deal_store_id'] = ''
    if not deal_groups.empty:
        for idx, row in result.iterrows():
            matching_deals = deal_groups[
                (deal_groups['start_cus_dt'] == row['date']) & 
                (deal_groups['included_products'].str.contains(row['asin'], na=False))
            ]
            if not matching_deals.empty:
                result.at[idx, 'deal'] = matching_deals['type'].iloc[0]
                result.at[idx, 'deal_store_id'] = matching_deals['store_id'].iloc[0]

    # Validate the output data
    is_valid, reason = validate_output(result)
    if not is_valid:
        logger.error(f"Output data validation failed: {reason}")
        raise ValueError(f"Output data validation failed: {reason}")

    return result

def combine_sc_vc(
    df_sc: pd.DataFrame,
    df_vc: pd.DataFrame
) -> pd.DataFrame:
    """
    Combine SC and VC data into a single wide table.

    Args:
        df_sc: DataFrame from sc_sale_coupon_deal
        df_vc: DataFrame from vc_sale_coupon_deal

    Returns:
        Combined DataFrame with columns:
        - asin: Product ASIN
        - date: Date of sale
        - price: Unit price (mode of SC/VC prices)
        - price_store_id: Store ID for the chosen price
        - volume: Combined sales volume
        - coupon: Main coupon info (highest discount)
        - coupon_details: All coupon information
        - coupon_count: Total number of coupons
        - deal: Deal information
        - deal_store_id: Store ID for the deal

    Notes:
        - If price has multiple modes, one is chosen randomly
        - For conflicting coupons, the highest discount is chosen
        - If discount types differ, one is chosen randomly
    """
    # Merge SC and VC data on ASIN and date
    df_combined = pd.merge(
        df_sc, df_vc,
        how='outer',
        on=['asin', 'date'],
        suffixes=('_sc', '_vc')
    )

    # Initialize result DataFrame
    result = pd.DataFrame()
    result['asin'] = df_combined['asin']
    result['date'] = df_combined['date']

    # Handle price conflicts using mode
    def get_price_mode(row):
        prices = []
        store_ids = []
        
        if pd.notna(row.get('price_sc')):
            prices.append(row['price_sc'])
            store_ids.append(row['price_store_id_sc'])
        if pd.notna(row.get('price_vc')):
            prices.append(row['price_vc'])
            store_ids.append(row['price_store_id_vc'])
            
        if not prices:
            return 0, ''
            
        # Calculate mode of prices
        price_counts = pd.Series(prices).value_counts()
        max_count = price_counts.max()
        mode_prices = price_counts[price_counts == max_count].index.tolist()
        
        # If multiple modes, randomly select one
        selected_price = np.random.choice(mode_prices)
        # Get corresponding store_id
        selected_store_id = store_ids[prices.index(selected_price)]
        
        return selected_price, selected_store_id

    # Apply price mode calculation
    result['price'] = df_combined.apply(get_price_mode, axis=1).str[0]
    result['price_store_id'] = df_combined.apply(get_price_mode, axis=1).str[1]

    # Combine volumes
    result['volume'] = df_combined.apply(
        lambda row: (
            (row.get('volume_sc', 0) if pd.notna(row.get('volume_sc')) else 0) +
            (row.get('volume_vc', 0) if pd.notna(row.get('volume_vc')) else 0)
        ),
        axis=1
    )

    # Process coupons
    def combine_coupons(row):
        coupons_sc = []
        coupons_vc = []
        details_sc = []
        details_vc = []
        
        if pd.notna(row.get('coupon_sc')):
            coupons_sc = [x.strip() for x in str(row['coupon_sc']).split(',') if x.strip()]
            if pd.notna(row.get('coupon_details_sc')):
                details_sc = [x.strip() for x in str(row['coupon_details_sc']).split(',') if x.strip()]
                
        if pd.notna(row.get('coupon_vc')):
            coupons_vc = [x.strip() for x in str(row['coupon_vc']).split(',') if x.strip()]
            if pd.notna(row.get('coupon_details_vc')):
                details_vc = [x.strip() for x in str(row['coupon_details_vc']).split(',') if x.strip()]

        all_coupons = coupons_sc + coupons_vc
        all_details = details_sc + details_vc
        
        if not all_coupons:
            return '', '', 0
            
        # Group coupons by discount type
        discount_groups = {}
        for coupon in all_coupons:
            if not coupon:
                continue
            # Extract amount using regex with error handling
            amount_match = re.match(r'(\d+\.?\d*)', coupon)
            if not amount_match:
                continue
            try:
                amount = float(amount_match.group(1))
            except (ValueError, AttributeError):
                continue

            # Extract discount type with error handling
            discount_match = re.search(r'[^\d\.]+$', coupon)
            if not discount_match:
                continue
            discount_type = discount_match.group(0)
            
            if discount_type not in discount_groups:
                discount_groups[discount_type] = []
            discount_groups[discount_type].append(amount)
            
        # Select highest discount for each type
        selected_coupons = []
        for dtype, amounts in discount_groups.items():
            selected_coupons.append(f"{max(amounts)}{dtype}")
            
        # If multiple types exist, randomly select one
        if len(selected_coupons) > 1:
            main_coupon = np.random.choice(selected_coupons)
        else:
            main_coupon = selected_coupons[0] if selected_coupons else ''
            
        return (
            main_coupon,
            ', '.join(all_details) if all_details else '',
            len(all_coupons)
        )

    # Apply coupon combination
    coupon_results = df_combined.apply(combine_coupons, axis=1)
    result['coupon'] = coupon_results.str[0]
    result['coupon_details'] = coupon_results.str[1]
    result['coupon_count'] = coupon_results.str[2]

    # Process deals
    def combine_deals(row):
        if pd.notna(row.get('deal_sc')) and row['deal_sc']:
            return row['deal_sc'], row['deal_store_id_sc']
        elif pd.notna(row.get('deal_vc')) and row['deal_vc']:
            return row['deal_vc'], row['deal_store_id_vc']
        return '', ''

    # Apply deal combination
    deal_results = df_combined.apply(combine_deals, axis=1)
    result['deal'] = deal_results.str[0]
    result['deal_store_id'] = deal_results.str[1]

    # Remove duplicates
    result = result.drop_duplicates(subset=['asin', 'date'])

    # Validate the output data
    is_valid, reason = validate_output(result)
    if not is_valid:
        logger.error(f"Output data validation failed: {reason}")
        raise ValueError(f"Output data validation failed: {reason}")
        
    return result
