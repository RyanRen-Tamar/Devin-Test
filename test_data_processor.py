import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_processor import (
    vc_sale_coupon_deal,
    sc_sale_coupon_deal,
    combine_sc_vc,
    validate_output
)

class TestDataProcessor(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        self.test_asins = ['B001', 'B002']
        self.start_date = '2024-01-01'
        self.end_date = '2024-01-10'
        
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

    def test_vc_sale_basic_functionality(self):
        """Test basic VC sales data processing functionality"""
        test_asins = ['B001']
        start_date = '2024-01-01'
        end_date = '2024-01-10'
        
        result = vc_sale_coupon_deal(test_asins, start_date, end_date)
        
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

    def test_sc_sale_basic_functionality(self):
        """Test basic SC sales data processing functionality"""
        test_asins = ['B002']
        start_date = '2024-01-01'
        end_date = '2024-01-10'
        
        result = sc_sale_coupon_deal(test_asins, start_date, end_date)
        
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
        empty_vc = vc_sale_coupon_deal([], start_date, end_date)
        self.assertTrue(empty_vc.empty)
        self.assertEqual(len(empty_vc.columns), len(required_columns))
        
        empty_sc = sc_sale_coupon_deal([], start_date, end_date)
        self.assertTrue(empty_sc.empty)
        self.assertEqual(len(empty_sc.columns), len(required_columns))
        
        # Test invalid date range
        invalid_vc = vc_sale_coupon_deal(['B001'], end_date, start_date)
        self.assertTrue(invalid_vc.empty)
        
        invalid_sc = sc_sale_coupon_deal(['B002'], end_date, start_date)
        self.assertTrue(invalid_sc.empty)
        
        # Test invalid ASIN format
        invalid_asin_vc = vc_sale_coupon_deal(['invalid'], start_date, end_date)
        self.assertTrue(invalid_asin_vc.empty)
        
        invalid_asin_sc = sc_sale_coupon_deal(['invalid'], start_date, end_date)
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
        df_sc_coupon.loc[0, 'coupon'] = '20%OFF'
        df_vc_coupon.loc[0, 'coupon'] = '15%OFF'
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon)
        self.assertEqual(result.loc[0, 'coupon'], '20%OFF')
        
        # Test different discount types
        df_sc_coupon.loc[1, 'coupon'] = '10%OFF'
        df_vc_coupon.loc[1, 'coupon'] = '¥50OFF'
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon)
        self.assertIn(result.loc[1, 'coupon'], ['10%OFF', '¥50OFF'])
        
        # Test coupon details combination
        df_sc_coupon.loc[2, 'coupon_details'] = 'SC Deal'
        df_vc_coupon.loc[2, 'coupon_details'] = 'VC Deal'
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon)
        self.assertTrue(
            'SC Deal' in result.loc[2, 'coupon_details'] and 
            'VC Deal' in result.loc[2, 'coupon_details']
        )
        
        # Test malformed coupon format handling
        df_sc_coupon.loc[3, 'coupon'] = 'INVALID'
        df_vc_coupon.loc[3, 'coupon'] = '25%OFF'
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon)
        self.assertEqual(result.loc[3, 'coupon'], '25%OFF')

    def test_sale_data_validation(self):
        """Test data validation for both VC and SC sales data"""
        try:
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
        prd_df = pd.DataFrame({
            'asin': ['B0XXXX'],
            'date': ['2025-01-01'],
            'price': [19.99],
            'price_store_id': [12345],
            'volume': [500],
            'coupon': ['10% Off'],
            'coupon_details': ['10% Off, ¥5 Off'],
            'coupon_count': [2],
            'deal': ['Best Deal'],
            'deal_store_id': [54321]
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
