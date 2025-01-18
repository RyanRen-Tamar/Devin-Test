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

    def test_combine_sc_vc_coupon_selection(self):
        """Test coupon selection logic in combine_sc_vc"""
        # Create test data with different discount types
        df_sc_coupon = self.df_sc.copy()
        df_vc_coupon = self.df_vc.copy()
        
        # Set specific coupons for testing
        df_sc_coupon.loc[0, 'coupon'] = '20%OFF'
        df_vc_coupon.loc[0, 'coupon'] = '15%OFF'
        
        result = combine_sc_vc(df_sc_coupon, df_vc_coupon)
        
        # Check that higher discount was selected
        self.assertIn(result.loc[0, 'coupon'], ['20%OFF', '15%OFF'])

    def test_vc_sale_coupon_deal(self):
        """Test VC sales data processing"""
        try:
            result = vc_sale_coupon_deal(
                self.test_asins,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            # Check DataFrame structure
            required_columns = [
                'asin', 'date', 'price', 'price_store_id', 'volume',
                'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
            ]
            for col in required_columns:
                self.assertIn(col, result.columns)
            
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
            self.fail(f"vc_sale_coupon_deal raised an error: {str(e)}")

    def test_sc_sale_coupon_deal(self):
        """Test SC sales data processing"""
        try:
            result = sc_sale_coupon_deal(
                self.test_asins,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            # Check DataFrame structure
            required_columns = [
                'asin', 'date', 'price', 'price_store_id', 'volume',
                'coupon', 'coupon_details', 'coupon_count', 'deal', 'deal_store_id'
            ]
            for col in required_columns:
                self.assertIn(col, result.columns)
            
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
            self.fail(f"sc_sale_coupon_deal raised an error: {str(e)}")

if __name__ == '__main__':
    unittest.main()
