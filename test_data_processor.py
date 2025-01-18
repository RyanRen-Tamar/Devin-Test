import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_processor import (
    vc_sale_coupon_deal,
    sc_sale_coupon_deal,
    combine_sc_vc,
    validate_output
)

# Mock data for testing
MOCK_VC_DATA = [
    {
        'asin': 'B001',
        'start_date': '2024-01-01',
        'ordered_revenue': 1999.0,
        'ordered_units': 100,
        'store_id': 'VC001'
    }
]

MOCK_SC_DATA = [
    {
        'asin': 'B002',
        'cus_date': '2024-01-01',
        'ordered_product_sales_amount': 2999.0,
        'units_ordered': 100,
        'store_id': 'SC001'
    }
]

MOCK_COUPON_DATA = [
    {
        'start_cus_dt': '2024-01-01',
        'asins': 'B001,B002',
        'discount_amount': 20,  # Changed to match test expectations
        'discount_type': '%OFF',
        'name': 'Test Coupon'
    }
]

MOCK_DEAL_DATA = [
    {
        'start_cus_dt': '2024-01-01',
        'included_products': 'B001,B002',
        'type': 'Lightning Deal',
        'store_id': 'DS001'
    }
]

class TestDataProcessor(unittest.TestCase):
    def setUp(self):
        """Set up test data and mocks"""
        self.test_asins = ['B001', 'B002']
        self.start_date = '2024-01-01'
        self.end_date = '2024-01-07'  # 7 days of data
        
        # Create mock connection and cursor
        self.mock_cursor = MagicMock()
        self.mock_connection = MagicMock()
        self.mock_connection.cursor.return_value.__enter__.return_value = self.mock_cursor
        
        # Set up mock cursor to return our test data
        def mock_execute(sql, *args, **kwargs):
            self.mock_cursor.last_executed_sql = sql.lower()
            
        def mock_fetchall():
            sql = getattr(self.mock_cursor, 'last_executed_sql', '').lower()
            if 'sp_store_report_get_vendor_sales' in sql:
                # Check for invalid ASIN in the WHERE clause
                if "asin in" in sql.lower():
                    try:
                        # Extract everything between "asin in (" and the next ")"
                        asin_clause = sql.lower().split("asin in (")[1].split(")")[0]
                        # Split by comma and clean up each ASIN
                        asin_list = [p.strip().strip("'").strip('"') for p in asin_clause.split(",")]
                        if any(asin == 'invalid' for asin in asin_list):
                            return []
                    except IndexError:
                        # If SQL parsing fails, assume no data
                        return []
                # Generate 7 days of data
                base_data = MOCK_VC_DATA[0].copy()
                result = []
                for i in range(7):
                    day_data = base_data.copy()
                    day_data['start_date'] = f'2024-01-{i+1:02d}'
                    result.append(day_data)
                return result
            elif 'sp_store_report_flat_file_all_orders_data_by_order_date_general' in sql:
                # Check for invalid ASIN in the WHERE clause
                if "asin in" in sql.lower():
                    try:
                        # Extract everything between "asin in (" and the next ")"
                        asin_clause = sql.lower().split("asin in (")[1].split(")")[0]
                        # Split by comma and clean up each ASIN
                        asin_list = [p.strip().strip("'").strip('"') for p in asin_clause.split(",")]
                        if any(asin == 'invalid' for asin in asin_list):
                            return []
                    except IndexError:
                        # If SQL parsing fails, assume no data
                        return []
                    # Only generate data if no invalid ASINs found
                    if any(asin == 'invalid' for asin in asin_list):
                        return []
                # Generate 7 days of data
                base_data = MOCK_SC_DATA[0].copy()
                result = []
                for i in range(7):
                    day_data = base_data.copy()
                    day_data['cus_date'] = f'2024-01-{i+1:02d}'
                    result.append(day_data)
                return result
            elif 'sp_store_report_get_coupon_performance_report' in sql:
                # Check for invalid ASIN in the JSON_CONTAINS clause
                if "json_contains" in sql.lower():
                    asin_list = [p.strip("'") for p in sql.lower().split("json_object('asin', ")[1:]]
                    asin_list = [a.split("'")[0] for a in asin_list]
                    if any(asin == 'invalid' for asin in asin_list):
                        return []
                # Generate 7 days of coupon data
                result = []
                for i in range(7):
                    day_data = MOCK_COUPON_DATA[0].copy()
                    day_data['start_cus_dt'] = f'2024-01-{i+1:02d}'
                    result.append(day_data)
                return result
            elif 'sp_store_report_get_promotion_performance_report' in sql:
                # Check for invalid ASIN in the JSON_CONTAINS clause
                if "json_contains" in sql.lower():
                    asin_list = [p.strip("'") for p in sql.lower().split("json_object('asin', ")[1:]]
                    asin_list = [a.split("'")[0] for a in asin_list]
                    if any(asin == 'invalid' for asin in asin_list):
                        return []
                # Generate 7 days of deal data
                result = []
                for i in range(7):
                    day_data = MOCK_DEAL_DATA[0].copy()
                    day_data['start_cus_dt'] = f'2024-01-{i+1:02d}'
                    result.append(day_data)
                return result
            return []
            
        self.mock_cursor.execute = mock_execute
        self.mock_cursor.fetchall = mock_fetchall
        
        # Install mock connection
        from data_fetcher import set_mock_connection
        set_mock_connection(self.mock_connection)
        
        # Create sample DataFrames that match the expected output format
        dates = pd.date_range(start=self.start_date, end=self.end_date)
        self.df_vc = pd.DataFrame({
            'asin': ['B001'] * len(dates),
            'date': dates,
            'price': [19.99] * len(dates),
            'price_store_id': ['VC001'] * len(dates),
            'volume': [100] * len(dates),
            'coupon': ['10%OFF'] * len(dates),
            'coupon_details': ['New Year Sale'] * len(dates),
            'coupon_count': [1] * len(dates),
            'deal': ['DEAL1'] * len(dates),
            'deal_store_id': ['DS001'] * len(dates)
        })
        
        self.df_sc = pd.DataFrame({
            'asin': ['B002'] * len(dates),
            'date': dates,
            'price': [29.99] * len(dates),
            'price_store_id': ['SC001'] * len(dates),
            'volume': [200] * len(dates),
            'coupon': ['20%OFF'] * len(dates),
            'coupon_details': ['Winter Sale'] * len(dates),
            'coupon_count': [1] * len(dates),
            'deal': ['DEAL2'] * len(dates),
            'deal_store_id': ['DS002'] * len(dates)
        })
        
    def tearDown(self):
        """Clean up after tests"""
        from data_fetcher import set_mock_connection
        set_mock_connection(None)

    def test_validate_output_structure(self):
        """Test that validate_output correctly checks DataFrame structure"""
        # Test with valid DataFrame
        is_valid, reason = validate_output(self.df_vc)
        self.assertTrue(is_valid, f"Validation failed: {reason}")
        
        # Test with missing columns
        invalid_df = self.df_vc.drop(columns=['coupon', 'deal'])
        is_valid, reason = validate_output(invalid_df)
        self.assertFalse(is_valid)
        
        # Test with empty DataFrame
        empty_df = pd.DataFrame()
        is_valid, reason = validate_output(empty_df)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "EMPTY_DATAFRAME")

    @patch('data_processor.fetch_sales_vc_data')
    @patch('data_processor.fetch_coupon_info')
    @patch('data_processor.fetch_deal_info')
    def test_vc_sale_basic_functionality(self, mock_deal, mock_coupon, mock_vc):
        """Test basic VC sales data processing functionality"""
        test_asins = ['B001']
        start_date = '2024-01-01'
        end_date = '2024-01-10'
        
        # Setup mocks
        # Generate 7 days of mock data
        mock_vc_data = []
        for i in range(7):
            day_data = MOCK_VC_DATA[0].copy()
            day_data['start_date'] = f'2024-01-{i+1:02d}'
            mock_vc_data.append(day_data)
        mock_vc.return_value = mock_vc_data
        
        # Generate 7 days of mock coupon data
        mock_coupon_data = []
        for i in range(7):
            day_data = MOCK_COUPON_DATA[0].copy()
            day_data['start_cus_dt'] = f'2024-01-{i+1:02d}'
            mock_coupon_data.append(day_data)
        mock_coupon.return_value = mock_coupon_data
        
        # Generate 7 days of mock deal data
        mock_deal_data = []
        for i in range(7):
            day_data = MOCK_DEAL_DATA[0].copy()
            day_data['start_cus_dt'] = f'2024-01-{i+1:02d}'
            mock_deal_data.append(day_data)
        mock_deal.return_value = mock_deal_data
        
        result = vc_sale_coupon_deal(test_asins, start_date, end_date, validation_enabled=False)
        
        # Check DataFrame structure
        required_columns = [
            'asin', 'date', 'price', 'price_store_id', 'volume',
            'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
        ]
        for col in required_columns:
            self.assertIn(col, result.columns)
            
        # Check price calculation
        self.assertTrue(all(result['price'] >= 0))
        
        # Check data types
        self.assertTrue(pd.api.types.is_string_dtype(result['asin']))
        self.assertTrue(pd.api.types.is_numeric_dtype(result['price']))
        self.assertTrue(pd.api.types.is_numeric_dtype(result['volume']))

    @patch('data_processor.fetch_sales_sc_data')
    @patch('data_processor.fetch_coupon_info')
    @patch('data_processor.fetch_deal_info')
    def test_sc_sale_basic_functionality(self, mock_deal, mock_coupon, mock_sc):
        """Test basic SC sales data processing functionality"""
        test_asins = ['B002']
        start_date = '2024-01-01'
        end_date = '2024-01-10'
        
        # Setup mocks
        # Generate 7 days of mock data
        mock_sc_data = []
        for i in range(7):
            day_data = MOCK_SC_DATA[0].copy()
            day_data['cus_date'] = f'2024-01-{i+1:02d}'
            mock_sc_data.append(day_data)
        mock_sc.return_value = mock_sc_data
        
        # Generate 7 days of mock coupon data
        mock_coupon_data = []
        for i in range(7):
            day_data = MOCK_COUPON_DATA[0].copy()
            day_data['start_cus_dt'] = f'2024-01-{i+1:02d}'
            mock_coupon_data.append(day_data)
        mock_coupon.return_value = mock_coupon_data
        
        # Generate 7 days of mock deal data
        mock_deal_data = []
        for i in range(7):
            day_data = MOCK_DEAL_DATA[0].copy()
            day_data['start_cus_dt'] = f'2024-01-{i+1:02d}'
            mock_deal_data.append(day_data)
        mock_deal.return_value = mock_deal_data
        
        result = sc_sale_coupon_deal(test_asins, start_date, end_date, validation_enabled=False)
        
        # Check DataFrame structure
        required_columns = [
            'asin', 'date', 'price', 'price_store_id', 'volume',
            'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
        ]
        for col in required_columns:
            self.assertIn(col, result.columns)
            
        # Check price calculation
        self.assertTrue(all(result['price'] >= 0))
        
        # Check data types
        self.assertTrue(pd.api.types.is_string_dtype(result['asin']))
        self.assertTrue(pd.api.types.is_numeric_dtype(result['price']))
        self.assertTrue(pd.api.types.is_numeric_dtype(result['volume']))

    def test_sale_data_edge_cases(self):
        """Test edge cases for both VC and SC data processing"""
        start_date = '2024-01-01'
        end_date = '2024-01-10'
        required_columns = [
            'asin', 'date', 'price', 'price_store_id', 'volume',
            'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
        ]
        
        # Test empty input
        empty_vc = vc_sale_coupon_deal([], start_date, end_date, validation_enabled=False)
        self.assertTrue(empty_vc.empty, "Empty VC input should return empty DataFrame")
        self.assertEqual(
            sorted(empty_vc.columns.tolist()),
            sorted(required_columns),
            "Empty VC DataFrame should have all required columns"
        )
        
        empty_sc = sc_sale_coupon_deal([], start_date, end_date, validation_enabled=False)
        self.assertTrue(empty_sc.empty, "Empty SC input should return empty DataFrame")
        self.assertEqual(
            sorted(empty_sc.columns.tolist()),
            sorted(required_columns),
            "Empty SC DataFrame should have all required columns"
        )
        
        # Test invalid date range
        invalid_vc = vc_sale_coupon_deal(['B001'], end_date, start_date, validation_enabled=False)
        self.assertTrue(invalid_vc.empty)
        
        invalid_sc = sc_sale_coupon_deal(['B002'], end_date, start_date, validation_enabled=False)
        self.assertTrue(invalid_sc.empty)
        
        # Test invalid ASIN format
        invalid_asin_vc = vc_sale_coupon_deal(['invalid'], start_date, end_date, validation_enabled=False)
        self.assertTrue(invalid_asin_vc.empty)
        
        invalid_asin_sc = sc_sale_coupon_deal(['invalid'], start_date, end_date, validation_enabled=False)
        self.assertTrue(invalid_asin_sc.empty)

    def test_combine_sc_vc_structure(self):
        """Test that combine_sc_vc produces correct output structure"""
        try:
            result = combine_sc_vc(self.df_sc, self.df_vc)
            
            # Check required columns
            required_columns = [
                'asin', 'date', 'price', 'price_store_id', 'volume',
                'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
            ]
            for col in required_columns:
                self.assertIn(col, result.columns)
                
            # Check no duplicates
            self.assertEqual(
                len(result),
                len(result.drop_duplicates(subset=['asin', 'date']))
            )
            
            # Check volume combination
            self.assertTrue(all(result['volume'] >= 0))
            
            # Check data types match PRD requirements
            self.assertTrue(pd.api.types.is_string_dtype(result['asin']))
            self.assertTrue(pd.api.types.is_numeric_dtype(result['price']))
            self.assertTrue(pd.api.types.is_numeric_dtype(result['volume']))
            self.assertTrue(pd.api.types.is_string_dtype(result['coupon']))
            self.assertTrue(pd.api.types.is_string_dtype(result['deal']))
            
            # Test empty input handling
            empty_result = combine_sc_vc(pd.DataFrame(), pd.DataFrame())
            self.assertTrue(empty_result.empty)
            self.assertEqual(len(empty_result.columns), len(required_columns))
            
        except ValueError as e:
            self.fail(f"combine_sc_vc raised ValueError: {str(e)}")

    def test_combine_sc_vc_price_mode(self):
        """Test price mode calculation in combine_sc_vc"""
        # Create test data with known price modes
        df_sc_price = self.df_sc.copy()
        df_vc_price = self.df_vc.copy()
        
        # Set specific prices for testing mode
        df_sc_price.loc[0:2, 'price'] = 10.0
        df_vc_price.loc[0:2, 'price'] = 10.0
        
        result = combine_sc_vc(df_sc_price, df_vc_price)
        
        # Check that mode was calculated correctly
        self.assertEqual(result.loc[0, 'price'], 10.0)
        
        # Test multiple modes scenario
        df_sc_price.loc[3:4, 'price'] = 20.0
        df_vc_price.loc[3:4, 'price'] = 30.0
        result = combine_sc_vc(df_sc_price, df_vc_price)
        self.assertIn(result.loc[3, 'price'], [20.0, 30.0])
        
        # Test missing price handling
        df_sc_price.loc[5, 'price'] = np.nan
        df_vc_price.loc[5, 'price'] = 40.0
        result = combine_sc_vc(df_sc_price, df_vc_price)
        self.assertEqual(result.loc[5, 'price'], 40.0)

    def test_combine_sc_vc_coupon_selection(self):
        """Test coupon selection logic in combine_sc_vc"""
        # Create test data with different discount types
        df_sc_coupon = self.df_sc.copy()
        df_vc_coupon = self.df_vc.copy()
        
        # Test highest discount selection
        df_sc_coupon = pd.DataFrame({
            'asin': ['B001'],
            'date': ['2024-01-01'],
            'price': [19.99],
            'price_store_id': ['SC001'],
            'volume': [100],
            'coupon': ['20%OFF'],
            'coupon_details': ['SC Deal'],
            'coupon_count': [1],
            'deal': ['DEAL1'],
            'deal_store_id': ['DS001']
        })
        df_vc_coupon = pd.DataFrame({
            'asin': ['B001'],
            'date': ['2024-01-01'],
            'price': [19.99],
            'price_store_id': ['VC001'],
            'volume': [100],
            'coupon': ['15%OFF'],
            'coupon_details': ['VC Deal'],
            'coupon_count': [1],
            'deal': ['DEAL1'],
            'deal_store_id': ['DS001']
        })
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon, validation_enabled=False)
        self.assertEqual(result.loc[0, 'coupon'], '20%OFF')
        
        # Test different discount types
        df_sc_coupon = pd.DataFrame({
            'asin': ['B001'],
            'date': ['2024-01-01'],
            'price': [19.99],
            'price_store_id': ['SC001'],
            'volume': [100],
            'coupon': ['10%OFF'],
            'coupon_details': ['SC Deal'],
            'coupon_count': [1],
            'deal': ['DEAL1'],
            'deal_store_id': ['DS001']
        })
        df_vc_coupon = pd.DataFrame({
            'asin': ['B001'],
            'date': ['2024-01-01'],
            'price': [19.99],
            'price_store_id': ['VC001'],
            'volume': [100],
            'coupon': ['¥50OFF'],
            'coupon_details': ['VC Deal'],
            'coupon_count': [1],
            'deal': ['DEAL1'],
            'deal_store_id': ['DS001']
        })
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon, validation_enabled=False)
        self.assertIn(result.iloc[0]['coupon'], ['10%OFF', '¥50OFF'])
        
        # Test coupon details combination
        df_sc_coupon = pd.DataFrame({
            'asin': ['B001'],
            'date': ['2024-01-01'],
            'price': [19.99],
            'price_store_id': ['SC001'],
            'volume': [100],
            'coupon': ['10%OFF'],
            'coupon_details': ['SC Deal'],
            'coupon_count': [1],
            'deal': ['DEAL1'],
            'deal_store_id': ['DS001']
        })
        df_vc_coupon = pd.DataFrame({
            'asin': ['B001'],
            'date': ['2024-01-01'],
            'price': [19.99],
            'price_store_id': ['VC001'],
            'volume': [100],
            'coupon': ['15%OFF'],
            'coupon_details': ['VC Deal'],
            'coupon_count': [1],
            'deal': ['DEAL1'],
            'deal_store_id': ['DS001']
        })
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon, validation_enabled=False)
        self.assertTrue(
            'SC Deal' in result.iloc[0]['coupon_details'] and 
            'VC Deal' in result.iloc[0]['coupon_details']
        )
        
        # Test malformed coupon format handling
        df_sc_coupon = pd.DataFrame({
            'asin': ['B001'],
            'date': ['2024-01-01'],
            'price': [19.99],
            'price_store_id': ['SC001'],
            'volume': [100],
            'coupon': ['INVALID'],
            'coupon_details': ['SC Deal'],
            'coupon_count': [1],
            'deal': ['DEAL1'],
            'deal_store_id': ['DS001']
        })
        df_vc_coupon = pd.DataFrame({
            'asin': ['B001'],
            'date': ['2024-01-01'],
            'price': [19.99],
            'price_store_id': ['VC001'],
            'volume': [100],
            'coupon': ['25%OFF'],
            'coupon_details': ['VC Deal'],
            'coupon_count': [1],
            'deal': ['DEAL1'],
            'deal_store_id': ['DS001']
        })
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon, validation_enabled=False)
        self.assertEqual(result.iloc[0]['coupon'], '25%OFF')

    @patch('data_processor.fetch_sales_vc_data')
    @patch('data_processor.fetch_sales_sc_data')
    @patch('data_processor.fetch_coupon_info')
    @patch('data_processor.fetch_deal_info')
    def test_sale_data_validation(self, mock_deal, mock_coupon, mock_sc, mock_vc):
        """Test data validation for both VC and SC sales data"""
        try:
            # Generate 7 days of mock data
            mock_vc_data = []
            mock_sc_data = []
            mock_coupon_data = []
            mock_deal_data = []
            
            for i in range(7):
                # VC data
                vc_day = MOCK_VC_DATA[0].copy()
                vc_day['start_date'] = f'2024-01-{i+1:02d}'
                mock_vc_data.append(vc_day)
                
                # SC data
                sc_day = MOCK_SC_DATA[0].copy()
                sc_day['cus_date'] = f'2024-01-{i+1:02d}'
                mock_sc_data.append(sc_day)
                
                # Coupon data
                coupon_day = MOCK_COUPON_DATA[0].copy()
                coupon_day['start_cus_dt'] = f'2024-01-{i+1:02d}'
                mock_coupon_data.append(coupon_day)
                
                # Deal data
                deal_day = MOCK_DEAL_DATA[0].copy()
                deal_day['start_cus_dt'] = f'2024-01-{i+1:02d}'
                mock_deal_data.append(deal_day)
            
            mock_vc.return_value = mock_vc_data
            mock_sc.return_value = mock_sc_data
            mock_coupon.return_value = mock_coupon_data
            mock_deal.return_value = mock_deal_data
            
            # Test VC data validation
            vc_result = vc_sale_coupon_deal(
                self.test_asins,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            # Test SC data validation
            sc_result = sc_sale_coupon_deal(
                self.test_asins,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            for result in [vc_result, sc_result]:
                # Check data types
                self.assertTrue(pd.api.types.is_numeric_dtype(result['price']))
                self.assertTrue(pd.api.types.is_numeric_dtype(result['volume']))
                self.assertTrue(pd.api.types.is_numeric_dtype(result['coupon_count']))
                
                # Check value ranges
                self.assertTrue(all(result['price'] >= 0))
                self.assertTrue(all(result['volume'] >= 0))
                self.assertTrue(all(result['coupon_count'] >= 0))
                
                # Verify ASIN filtering
                self.assertTrue(all(result['asin'].isin(self.test_asins)))
                
                # Verify date range
                if len(result) > 0:
                    min_date = pd.to_datetime(result['date']).min()
                    max_date = pd.to_datetime(result['date']).max()
                    self.assertGreaterEqual(
                        min_date,
                        pd.to_datetime(self.start_date)
                    )
                    self.assertLessEqual(
                        max_date,
                        pd.to_datetime(self.end_date)
                    )
                    
        except Exception as e:
            self.fail(f"Data validation test failed: {str(e)}")

    def test_malformed_data_handling(self):
        """Test handling of malformed input data"""
        # Create malformed test data
        malformed_df = pd.DataFrame({
            'asin': ['B001', 'invalid', 'B002'],
            'date': ['2024-01-01', 'not-a-date', '2024-01-02'],
            'price': [10.0, 'invalid', -5.0],
            'price_store_id': [123, None, 456],
            'volume': [100, 'invalid', -10],
            'coupon': ['10%OFF', 'INVALID', None],
            'coupon_details': ['Test', None, 'Test2'],
            'coupon_count': [1, 'invalid', -1],
            'deal': ['Deal1', None, 'Deal2'],
            'deal_store_id': ['123', None, '456']
        })
        
        # Test combining malformed data
        result = combine_sc_vc(malformed_df, self.df_vc)
        
        # Verify data cleaning
        self.assertTrue(all(result['price'] >= 0))
        self.assertTrue(all(result['volume'] >= 0))
        self.assertTrue(all(result['coupon_count'] >= 0))
        self.assertTrue(pd.api.types.is_numeric_dtype(result['price']))
        self.assertTrue(pd.api.types.is_numeric_dtype(result['volume']))
        self.assertTrue(pd.api.types.is_numeric_dtype(result['coupon_count']))

    def test_prd_requirements(self):
        """Test output format against PRD requirements"""
        # Test data matching PRD example
        # Create test data with 7 days
        dates = pd.date_range(start='2025-01-01', periods=7)
        prd_df = pd.DataFrame({
            'asin': ['B0XXXX'] * 7,
            'date': dates,
            'price': [19.99] * 7,
            'price_store_id': [12345] * 7,
            'volume': [500] * 7,
            'coupon': ['10% Off'] * 7,
            'coupon_details': ['10% Off, ¥5 Off'] * 7,
            'coupon_count': [2] * 7,
            'deal': ['Best Deal'] * 7,
            'deal_store_id': [54321] * 7
        })
        
        # Validate against PRD format
        is_valid, reason = validate_output(prd_df)
        self.assertTrue(is_valid, f"PRD format validation failed: {reason}")
        
        # Check specific PRD requirements
        self.assertTrue(pd.api.types.is_string_dtype(prd_df['asin']))
        self.assertTrue(pd.api.types.is_numeric_dtype(prd_df['price']))
        self.assertTrue(pd.api.types.is_numeric_dtype(prd_df['volume']))
        self.assertTrue(pd.api.types.is_numeric_dtype(prd_df['coupon_count']))
        self.assertTrue(pd.api.types.is_string_dtype(prd_df['coupon']))
        self.assertTrue(pd.api.types.is_string_dtype(prd_df['deal']))
        
        # Test combined data matches PRD format
        combined_result = combine_sc_vc(self.df_sc, self.df_vc)
        is_valid, reason = validate_output(combined_result)
        self.assertTrue(is_valid, f"Combined data format validation failed: {reason}")

if __name__ == '__main__':
    unittest.main()
