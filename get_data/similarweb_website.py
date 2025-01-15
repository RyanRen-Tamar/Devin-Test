import os
import sys
import json
import math
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parents[1]))

import requests
from functions.mysql_config import mysql_connect_init, insert_data
from functions.setting import logger


def load_api_config() -> Dict[str, str]:
    """Load SimilarWeb API configuration"""
    try:
        config_path = Path(__file__).resolve().parents[1] / 'functions' / 'data.json'
        logger.info(f"Attempting to load API config from {config_path}")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            api_key = config.get('similarweb_api_config', {}).get('similarweb_api_key')
            
            if api_key:
                logger.info("Successfully loaded API key")
                logger.debug(f"API key: {api_key[:4]}...{api_key[-4:]}")
            else:
                logger.warning("similarweb_api_key not found in config")
                
            return {"api_key": api_key}
            
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config file: {config_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to load API config: {str(e)}")
        raise


class SimilarWebWebsiteCollector:
    """SimilarWeb Websites Dataset collector"""
    
    def __init__(self):
        """Initialize the collector"""
        self.base_url = "https://api.similarweb.com/batch/v4/request-report"
        config = load_api_config()
        self.api_key = config["api_key"]
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": self.api_key
        }
        self.db_conn = mysql_connect_init()
        
    def _make_request(self, vtable: str, domain: str, country: str, 
                     granularity: str = "MONTHLY", 
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> Dict:
        """Make API request to SimilarWeb
        
        Args:
            vtable: Virtual table name (e.g., "traffic_and_engagement")
            domain: Website domain
            country: Country code
            granularity: Data granularity (DAILY/WEEKLY/MONTHLY)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dict: API response data
        """
        try:
            payload = {
                "vtable": vtable,
                "domains": [domain],
                "countries": [country],
                "granularity": granularity
            }
            
            if start_date:
                payload["start_date"] = start_date
            if end_date:
                payload["end_date"] = end_date
                
            logger.info(f"Making request to {vtable}")
            logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data:
                logger.warning(f"Empty response for {vtable}")
                return {}
                
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            logger.error(f"Response content: {response.text if response else 'No response'}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response content: {response.text}")
            raise
        except Exception as e:
            logger.error(f"Other error: {str(e)}")
            raise
            
    def _save_to_db(self, task_id: str, domain: str, country: str,
                    traffic_data: Dict, marketing_data: Dict,
                    similar_sites_data: Dict, website_data: Dict,
                    geo_data: Dict, sources_data: Dict) -> int:
        """Save collected data to database
        
        Args:
            task_id: Task identifier
            domain: Website domain
            country: Country code
            traffic_data: Traffic & engagement metrics
            marketing_data: Marketing channels data
            similar_sites_data: Similar sites data
            website_data: Website description data
            geo_data: Geographic distribution data
            sources_data: Traffic sources data
            
        Returns:
            int: Number of affected rows
        """
        if not any([traffic_data, marketing_data, similar_sites_data,
                   website_data, geo_data, sources_data]):
            return 0
            
        # Ensure task_id is numeric
        task_id = ''.join(filter(str.isdigit, task_id))
        if not task_id:
            raise ValueError(f"Invalid task_id format: {task_id}")
            
        insert_sql = """
        INSERT INTO test.similarweb_website_traffic_engagement (
            task_id, domain, country, date_month, granularity,
            -- Traffic & Engagement metrics
            all_traffic_visits, desktop_visits, mobile_visits,
            all_page_views, desktop_page_views, mobile_page_views,
            all_traffic_pages_per_visit, desktop_pages_per_visit, mobile_pages_per_visit,
            all_traffic_average_visit_duration, desktop_average_visit_duration, mobile_average_visit_duration,
            all_traffic_bounce_rate, desktop_bounce_rate, mobile_bounce_rate,
            desktop_unique_visitors, mobile_unique_visitors, deduplicated_audience,
            desktop_share, mobile_share,
            desktop_ppc_spend_usd, mobile_ppc_spend_usd,
            desktop_new_visitors, desktop_returning_visitors,
            global_rank, country_rank, category_rank_new, category,
            -- Marketing Channels
            desktop_marketing_channels_visits, mobile_marketing_channels_visits,
            desktop_marketing_channels_share, mobile_marketing_channels_share,
            channel_name, marketing_channels_data,
            -- Similar Sites
            similar_sites_data,
            -- Website
            site_description, online_revenue, category_rank, tags,
            -- Geographic
            desktop_top_geo,
            -- Traffic Sources
            desktop_traffic_sources, mobile_traffic_sources
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s
        )
        """
        
        try:
            values = []
            date_month = datetime.now().strftime('%Y-%m-01')  # First day of current month
            
            # Extract metrics from each dataset
            traffic = traffic_data.get('data', {}).get('traffic', {})
            marketing = marketing_data.get('data', {}).get('marketing', {})
            similar = similar_sites_data.get('data', {}).get('similar_sites', {})
            website = website_data.get('data', {}).get('website', {})
            geo = geo_data.get('data', {}).get('geo', {})
            sources = sources_data.get('data', {}).get('sources', {})
            
            values.append((
                int(task_id),
                domain,
                country,
                date_month,
                'MONTHLY',  # Default granularity
                
                # Traffic & Engagement
                traffic.get('all_traffic_visits'),
                traffic.get('desktop_visits'),
                traffic.get('mobile_visits'),
                traffic.get('all_page_views'),
                traffic.get('desktop_page_views'),
                traffic.get('mobile_page_views'),
                traffic.get('all_traffic_pages_per_visit'),
                traffic.get('desktop_pages_per_visit'),
                traffic.get('mobile_pages_per_visit'),
                traffic.get('all_traffic_average_visit_duration'),
                traffic.get('desktop_average_visit_duration'),
                traffic.get('mobile_average_visit_duration'),
                traffic.get('all_traffic_bounce_rate'),
                traffic.get('desktop_bounce_rate'),
                traffic.get('mobile_bounce_rate'),
                traffic.get('desktop_unique_visitors'),
                traffic.get('mobile_unique_visitors'),
                traffic.get('deduplicated_audience'),
                traffic.get('desktop_share'),
                traffic.get('mobile_share'),
                traffic.get('desktop_ppc_spend_usd'),
                traffic.get('mobile_ppc_spend_usd'),
                traffic.get('desktop_new_visitors'),
                traffic.get('desktop_returning_visitors'),
                traffic.get('global_rank'),
                traffic.get('country_rank'),
                traffic.get('category_rank_new'),
                traffic.get('category'),
                
                # Marketing Channels
                marketing.get('desktop_marketing_channels_visits'),
                marketing.get('mobile_marketing_channels_visits'),
                marketing.get('desktop_marketing_channels_share'),
                marketing.get('mobile_marketing_channels_share'),
                marketing.get('channel_name'),
                json.dumps(marketing) if marketing else None,
                
                # Similar Sites
                json.dumps(similar) if similar else None,
                
                # Website
                json.dumps(website.get('description')) if website.get('description') else None,
                json.dumps(website.get('online_revenue')) if website.get('online_revenue') else None,
                json.dumps(website.get('category_rank')) if website.get('category_rank') else None,
                json.dumps(website.get('tags')) if website.get('tags') else None,
                
                # Geographic
                json.dumps(geo) if geo else None,
                
                # Traffic Sources
                json.dumps(sources.get('desktop')) if sources.get('desktop') else None,
                json.dumps(sources.get('mobile')) if sources.get('mobile') else None
            ))
            
            return insert_data(self.db_conn, insert_sql, values)
            
        except Exception as e:
            logger.error(f"Database insertion failed: {str(e)}")
            logger.error(f"First row values: {values[0] if values else 'No values'}")
            raise
            
    def run(self, task_id: str, domain: str, country: str = "us",
            granularity: str = "MONTHLY",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None) -> Dict[str, Any]:
        """Run data collection task
        
        Args:
            task_id: Task identifier
            domain: Website domain
            country: Country code (default: "us")
            granularity: Data granularity (default: "MONTHLY")
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            Dict with summary and content
        """
        try:
            logger.info(f"Starting task {task_id}")
            
            # Collect data from all tables
            traffic_data = self._make_request(
                "traffic_and_engagement", domain, country,
                granularity, start_date, end_date
            )
            
            marketing_data = self._make_request(
                "marketing_channels", domain, country,
                granularity, start_date, end_date
            )
            
            similar_sites_data = self._make_request(
                "similar_sites", domain, country,
                granularity, start_date, end_date
            )
            
            website_data = self._make_request(
                "website", domain, country,
                granularity, start_date, end_date
            )
            
            geo_data = self._make_request(
                "desktop_top_geo", domain, country,
                granularity, start_date, end_date
            )
            
            sources_data = self._make_request(
                "traffic_sources", domain, country,
                granularity, start_date, end_date
            )
            
            # Save to database
            affected_rows = self._save_to_db(
                task_id, domain, country,
                traffic_data, marketing_data,
                similar_sites_data, website_data,
                geo_data, sources_data
            )
            
            logger.info(f"Task {task_id} completed, saved {affected_rows} rows")
            
            # Combine all data for response
            combined_data = {
                "traffic_and_engagement": traffic_data,
                "marketing_channels": marketing_data,
                "similar_sites": similar_sites_data,
                "website": website_data,
                "desktop_top_geo": geo_data,
                "traffic_sources": sources_data
            }
            
            return {
                "summary": {
                    "total_items": affected_rows,
                    "domain": domain,
                    "country": country,
                    "granularity": granularity,
                    "start_date": start_date,
                    "end_date": end_date
                },
                "content": combined_data
            }
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {str(e)}")
            raise
            
        finally:
            if hasattr(self, 'db_conn'):
                self.db_conn.close()


def generate_test_task_id() -> str:
    """Generate test task ID
    Returns:
        str: 24-digit string format: 1004(prefix) + YYYYMMDDHHMMSS(timestamp) + NNNNNN(random)
    """
    timestamp = time.strftime('%Y%m%d%H%M%S')
    random_num = str(random.randint(0, 999999)).zfill(6)
    return f"1004{timestamp}{random_num}"  # 1004 prefix for SimilarWeb collector


if __name__ == '__main__':
    help_text = """
    Usage: 
    1. Test Mode: 
       python similarweb_website.py --test <domain> [country] [granularity] [start_date] [end_date]
       Example: python similarweb_website.py --test amazon.com us MONTHLY 2024-01-01 2024-01-31
       
       
    2. Production Mode (via ETL service):
       python similarweb_website.py <domain> [country] [granularity] [start_date] [end_date]
       
    Parameters:
    - domain: Website domain (e.g., amazon.com)
    - country: Country code (default: us)
    - granularity: Data granularity (DAILY/WEEKLY/MONTHLY, default: MONTHLY)
    - start_date: Start date in YYYY-MM-DD format (optional)
    - end_date: End date in YYYY-MM-DD format (optional)
    """
    
    if len(sys.argv) < 2:
        print(help_text)
        sys.exit(1)
        
    # Check for test mode
    is_test_mode = '--test' in sys.argv
    if is_test_mode:
        sys.argv.remove('--test')
        
    # Parse arguments
    domain = sys.argv[1]
    country = sys.argv[2] if len(sys.argv) > 2 else "us"
    granularity = sys.argv[3] if len(sys.argv) > 3 else "MONTHLY"
    start_date = sys.argv[4] if len(sys.argv) > 4 else None
    end_date = sys.argv[5] if len(sys.argv) > 5 else None
    
    collector = SimilarWebWebsiteCollector()
    
    if is_test_mode:
        test_task_id = generate_test_task_id()
        logger.warning(f"Running in test mode with task_id: {test_task_id}")
        logger.warning("Note: This is a test run. Data will be marked with test prefix.")
    else:
        logger.warning("Running in production mode. Recommended to run through ETL service.")
        test_task_id = generate_test_task_id()
        
    result = collector.run(
        task_id=test_task_id,
        domain=domain,
        country=country,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date
    )
    
    print(json.dumps(result, indent=2))
