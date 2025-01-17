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
    """Load SimilarWeb API configuration for both Batch and REST APIs"""
    try:
        config_path = Path(__file__).resolve().parents[1] / 'functions' / 'data.json'
        logger.info(f"Attempting to load API config from {config_path}")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            api_config = config.get('similarweb_api_config', {})
            batch_api_key = api_config.get('similarweb_batch_api_key')
            rest_api_key = api_config.get('similarweb_rest_api_key')
            
            if batch_api_key and rest_api_key:
                logger.info("Successfully loaded both API keys")
                logger.debug(f"Batch API key: {batch_api_key[:4]}...{batch_api_key[-4:]}")
                logger.debug(f"REST API key: {rest_api_key[:4]}...{rest_api_key[-4:]}")
            else:
                missing = []
                if not batch_api_key:
                    missing.append("similarweb_batch_api_key")
                if not rest_api_key:
                    missing.append("similarweb_rest_api_key")
                logger.warning(f"Missing API keys: {', '.join(missing)}")
                
            return {
                "batch_api_key": batch_api_key,
                "rest_api_key": rest_api_key
            }
            
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
        # API endpoints
        self.batch_url = "https://api.similarweb.com/batch/v4/request-report"
        self.popular_pages_url = "https://api.similarweb.com/v4/website/{domain}/popular-pages"
        
        # Load API keys
        config = load_api_config()
        self.batch_api_key = config["batch_api_key"]
        self.rest_api_key = config["rest_api_key"]
        
        # Headers for different APIs
        self.batch_headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": self.batch_api_key
        }
        self.rest_headers = {
            "accept": "application/json",
            "api-key": self.rest_api_key
        }
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms (10 requests per second)
        
        # Database connection
        self.db_conn = mysql_connect_init()
        
        # Field to table mapping
        self.field_to_table_map = {
            # Traffic & Engagement fields
            "all_traffic_visits": "traffic_and_engagement",
            "desktop_visits": "traffic_and_engagement",
            "mobile_visits": "traffic_and_engagement",
            "all_page_views": "traffic_and_engagement",
            "desktop_page_views": "traffic_and_engagement",
            "mobile_page_views": "traffic_and_engagement",
            "all_traffic_pages_per_visit": "traffic_and_engagement",
            "desktop_pages_per_visit": "traffic_and_engagement",
            "mobile_pages_per_visit": "traffic_and_engagement",
            "all_traffic_average_visit_duration": "traffic_and_engagement",
            "desktop_average_visit_duration": "traffic_and_engagement",
            "mobile_average_visit_duration": "traffic_and_engagement",
            "all_traffic_bounce_rate": "traffic_and_engagement",
            "desktop_bounce_rate": "traffic_and_engagement",
            "mobile_bounce_rate": "traffic_and_engagement",
            "desktop_unique_visitors": "traffic_and_engagement",
            "mobile_unique_visitors": "traffic_and_engagement",
            "deduplicated_audience": "traffic_and_engagement",
            "desktop_share": "traffic_and_engagement",
            "mobile_share": "traffic_and_engagement",
            "desktop_ppc_spend_usd": "traffic_and_engagement",
            "mobile_ppc_spend_usd": "traffic_and_engagement",
            "desktop_new_visitors": "traffic_and_engagement",
            "desktop_returning_visitors": "traffic_and_engagement",
            
            # Marketing Channels fields
            "desktop_marketing_channels_visits": "marketing_channels",
            "mobile_marketing_channels_visits": "marketing_channels",
            "desktop_marketing_channels_share": "marketing_channels",
            "mobile_marketing_channels_share": "marketing_channels",
            "channel_name": "marketing_channels",
            
            # Similar Sites fields
            "similarity_score": "similar_sites",
            "overlap_score": "similar_sites",
            
            # Website fields
            "global_rank": "website",
            "country_rank": "website",
            "category_rank": "website",
            "category": "website",
            "site_description": "website",
            "online_revenue": "website",
            "tags": "website",
            
            # Geographic fields
            "desktop_top_geo": "desktop_top_geo",
            
            # Traffic Sources fields
            "desktop_traffic_sources": "traffic_sources",
            "mobile_traffic_sources": "traffic_sources",
            
            # Popular Pages fields (REST API)
            "popular_pages_url": "popular_pages",
            "popular_pages_traffic_share": "popular_pages"
        }
        
        # Field granularity support mapping
        self.field_granularity_support = {
            # Traffic & Engagement fields - support daily, weekly, monthly
            "all_traffic_visits": ["MONTHLY", "WEEKLY", "DAILY"],
            "desktop_visits": ["MONTHLY", "WEEKLY", "DAILY"],
            "mobile_visits": ["MONTHLY", "WEEKLY", "DAILY"],
            "all_page_views": ["MONTHLY", "WEEKLY", "DAILY"],
            "desktop_page_views": ["MONTHLY", "WEEKLY", "DAILY"],
            "mobile_page_views": ["MONTHLY", "WEEKLY", "DAILY"],
            "all_traffic_pages_per_visit": ["MONTHLY", "WEEKLY", "DAILY"],
            "desktop_pages_per_visit": ["MONTHLY", "WEEKLY", "DAILY"],
            "mobile_pages_per_visit": ["MONTHLY", "WEEKLY", "DAILY"],
            "all_traffic_average_visit_duration": ["MONTHLY", "WEEKLY", "DAILY"],
            "desktop_average_visit_duration": ["MONTHLY", "WEEKLY", "DAILY"],
            "mobile_average_visit_duration": ["MONTHLY", "WEEKLY", "DAILY"],
            "all_traffic_bounce_rate": ["MONTHLY", "WEEKLY", "DAILY"],
            "desktop_bounce_rate": ["MONTHLY", "WEEKLY", "DAILY"],
            "mobile_bounce_rate": ["MONTHLY", "WEEKLY", "DAILY"],
            "desktop_unique_visitors": ["MONTHLY", "WEEKLY", "DAILY"],
            "mobile_unique_visitors": ["MONTHLY", "WEEKLY", "DAILY"],
            "deduplicated_audience": ["MONTHLY", "WEEKLY", "DAILY"],
            "desktop_share": ["MONTHLY", "WEEKLY", "DAILY"],
            "mobile_share": ["MONTHLY", "WEEKLY", "DAILY"],
            "desktop_ppc_spend_usd": ["MONTHLY"],
            "mobile_ppc_spend_usd": ["MONTHLY"],
            "desktop_new_visitors": ["MONTHLY"],
            "desktop_returning_visitors": ["MONTHLY"],
            
            # All other fields - monthly only
            "desktop_marketing_channels_visits": ["MONTHLY"],
            "mobile_marketing_channels_visits": ["MONTHLY"],
            "desktop_marketing_channels_share": ["MONTHLY"],
            "mobile_marketing_channels_share": ["MONTHLY"],
            "channel_name": ["MONTHLY"],
            "similarity_score": ["MONTHLY"],
            "overlap_score": ["MONTHLY"],
            "global_rank": ["MONTHLY"],
            "country_rank": ["MONTHLY"],
            "category_rank": ["MONTHLY"],
            "category": ["MONTHLY"],
            "site_description": ["MONTHLY"],
            "online_revenue": ["MONTHLY"],
            "tags": ["MONTHLY"],
            "desktop_top_geo": ["MONTHLY"],
            "desktop_traffic_sources": ["MONTHLY"],
            "mobile_traffic_sources": ["MONTHLY"],
            "popular_pages_url": ["MONTHLY"],
            "popular_pages_traffic_share": ["MONTHLY"]
        }
        
    def _make_request(self, vtable: str, domain: str, country: str, 
                     granularity: str = "MONTHLY", 
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> Dict:
        """Make API request to SimilarWeb Batch API
        
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
            # Rate limiting
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
            
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
                self.batch_url,
                headers=self.batch_headers,
                json=payload
            )
            self.last_request_time = time.time()
            
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
                    geo_data: Dict, sources_data: Dict,
                    popular_pages_data: Dict, granularity: str = "MONTHLY") -> int:
        """Save collected data to database using REPLACE INTO for deduplication
        
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
            popular_pages_data: Popular pages data
            granularity: Data granularity (default: MONTHLY)
            
        Returns:
            int: Number of affected rows
        """
        if not any([traffic_data, marketing_data, similar_sites_data,
                   website_data, geo_data, sources_data, popular_pages_data]):
            return 0
            
        # Ensure task_id is numeric
        task_id = ''.join(filter(str.isdigit, task_id))
        if not task_id:
            raise ValueError(f"Invalid task_id format: {task_id}")
            
        # Get current date for date_month
        date_month = datetime.now().strftime('%Y-%m-01')
            
        insert_sql = """
        REPLACE INTO test.similarweb_website_traffic_engagement (
            -- Primary Key Fields
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
            desktop_traffic_sources, mobile_traffic_sources,
            
            -- Popular Pages
            popular_pages_data,
            
            -- Timestamps
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            NOW(), NOW()
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
                date_month,  # Using the date_month we defined earlier
                granularity,  # Using passed granularity parameter
                
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
                json.dumps(marketing, ensure_ascii=False) if marketing else None,
                
                # Similar Sites
                json.dumps(similar, ensure_ascii=False) if similar else None,
                
                # Website
                json.dumps(website.get('description'), ensure_ascii=False) if website.get('description') else None,
                json.dumps(website.get('online_revenue'), ensure_ascii=False) if website.get('online_revenue') else None,
                json.dumps(website.get('category_rank'), ensure_ascii=False) if website.get('category_rank') else None,
                json.dumps(website.get('tags'), ensure_ascii=False) if website.get('tags') else None,
                
                # Geographic
                json.dumps(geo, ensure_ascii=False) if geo else None,
                
                # Traffic Sources
                json.dumps(sources.get('desktop'), ensure_ascii=False) if sources.get('desktop') else None,
                json.dumps(sources.get('mobile'), ensure_ascii=False) if sources.get('mobile') else None,
                
                # Popular Pages
                json.dumps(popular_pages_data, ensure_ascii=False) if popular_pages_data else None
            ))
            
            return insert_data(self.db_conn, insert_sql, values)
            
        except Exception as e:
            logger.error(f"Database insertion failed: {str(e)}")
            logger.error(f"First row values: {values[0] if values else 'No values'}")
            raise
            
    def _validate_metrics_granularity(self, metrics: List[str], granularity: str) -> None:
        """Validate metrics against granularity

        Args:
            metrics: List of metrics to collect
            granularity: Data granularity (DAILY/WEEKLY/MONTHLY)

        Raises:
            ValueError: If any metric is not supported for the given granularity
        """
        # First validate fields exist
        valid_fields = set(self.field_to_table_map.keys())
        invalid_fields = [f for f in metrics if f not in valid_fields]
        if invalid_fields:
            raise ValueError(f"Invalid fields: {', '.join(invalid_fields)}. "
                          f"Valid fields are: {', '.join(sorted(valid_fields))}")

        # Then validate granularity support
        for field in metrics:
            supported_granularities = self.field_granularity_support[field]
            if granularity not in supported_granularities:
                raise ValueError(
                    f"Field {field} does not support {granularity} granularity. "
                    f"Supported: {', '.join(supported_granularities)}"
                )

        logger.info(f"Metrics {metrics} validated for granularity {granularity}")


    def _get_popular_pages(self, domain: str) -> Dict:
        """Get popular pages data using REST API
        
        This endpoint requires the Popular Pages add-on subscription.
        See: https://developers.similarweb.com/reference/popular-pages-desktop
        
        Args:
            domain: Website domain
            
        Returns:
            Dict: Popular pages data or empty dict if API fails
        """
        try:
            # Rate limiting (10 requests per second max)
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
            
            # Format URL with domain
            url = self.popular_pages_url.format(domain=domain)
            logger.info(f"Making Popular Pages API request for {domain}")
            
            # Make request with REST API key
            response = requests.get(
                url,
                headers=self.rest_headers,
                params={
                    "format": "json",
                    "main_domain_only": "true",  # Only get main domain pages
                    "limit": "100"  # Get up to 100 popular pages
                }
            )
            self.last_request_time = time.time()
            
            # Handle common error cases
            if response.status_code == 429:
                logger.error("Rate limit exceeded (429). Backing off...")
                time.sleep(1)  # Force 1 second delay
                return {}
            elif response.status_code == 403:
                logger.error("Access denied (403). Popular Pages add-on subscription required.")
                return {}
                
            response.raise_for_status()
            data = response.json()
            
            if not data:
                logger.warning(f"Empty response from Popular Pages API for {domain}")
                return {}
            
            # Extract and format popular pages data
            pages = []
            for page in data.get("pages", []):
                pages.append({
                    "url_path": page.get("url_path"),
                    "traffic_share": page.get("share"),
                    "title": page.get("title")
                })
            
            return {
                "total_pages": len(pages),
                "pages": pages
            }
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Popular Pages API request failed: {str(e)}")
            logger.warning("This endpoint requires the Popular Pages add-on subscription")
            return {}
        except Exception as e:
            logger.error(f"Popular Pages API error: {str(e)}")
            return {}

    def run(self, task_id: str, domain: str, metrics: List[str],
            country: str = "us", granularity: str = "MONTHLY",
            latest: bool = True,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None) -> Dict[str, Any]:
        """Run data collection task
        
        Args:
            task_id: Task identifier
            domain: Website domain
            metrics: List of metrics to collect
            country: Country code (default: "us")
            granularity: Data granularity (default: "MONTHLY")
            latest: If True, fetch only latest data without date range (default: True)
            start_date: Start date (optional, ignored if latest=True)
            end_date: End date (optional, ignored if latest=True)
            
        Returns:
            Dict with summary and content
        """
        try:
            logger.info(f"Starting task {task_id}")
            
            # Validate fields and granularity
            self._validate_metrics_granularity(metrics, granularity)
            
            from collections import defaultdict
            
            # Group requested fields by vtable for efficient API requests
            fields_by_vtable = defaultdict(list)
            for field in metrics:
                vtable = self.field_to_table_map[field]
                fields_by_vtable[vtable].append(field)
                
            # If latest is True, ignore start_date and end_date
            if latest:
                start_date = None
                end_date = None
            
            # Initialize data containers
            data = {
                "traffic_and_engagement": {},
                "marketing_channels": {},
                "similar_sites": {},
                "website": {},
                "desktop_top_geo": {},
                "traffic_sources": {},
                "popular_pages": {}
            }
            
            # Process each vtable
            for vtable, fields in fields_by_vtable.items():
                logger.info(f"Collecting data for vtable: {vtable} with fields: {fields}")
                
                if vtable == "popular_pages":
                    # Special handling for Popular Pages REST API
                    data[vtable] = self._get_popular_pages(domain)
                    continue
                    
                # For all other vtables, use Batch API
                response_data = self._make_request(
                    vtable=vtable,
                    domain=domain,
                    country=country,
                    granularity=granularity,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if response_data:
                    # Extract only requested fields
                    filtered_data = {}
                    for field in fields:
                        if field in response_data:
                            filtered_data[field] = response_data[field]
                    data[vtable] = filtered_data
                    logger.info(f"Successfully collected {len(filtered_data)} fields for {vtable}")
                else:
                    logger.warning(f"No data returned for {vtable}")
            
            # Save to database
            affected_rows = self._save_to_db(
                task_id, domain, country,
                data["traffic_and_engagement"],
                data["marketing_channels"],
                data["similar_sites"],
                data["website"],
                data["desktop_top_geo"],
                data["traffic_sources"],
                data["popular_pages"]
            )
            
            logger.info(f"Task {task_id} completed, saved {affected_rows} rows")
            
            # Return collected data
            return {
                "summary": {
                    "total_items": affected_rows,
                    "domain": domain,
                    "country": country,
                    "granularity": granularity,
                    "start_date": start_date,
                    "end_date": end_date,
                    "metrics": metrics,
                    "fields_by_table": {k: sorted(v) for k, v in fields_by_vtable.items()}
                },
                "content": data
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
       python similarweb_website.py --test <domain> <metrics> [country] [granularity] [start_date] [end_date]
       Example: python similarweb_website.py --test amazon.com "traffic,marketing,popular_pages" us MONTHLY 2024-01-01 2024-01-31
       
    2. Production Mode (via ETL service):
       python similarweb_website.py <domain> <metrics> [country] [granularity] [start_date] [end_date]
       
    Parameters:
    - domain: Website domain (e.g., amazon.com)
    - metrics: Comma-separated list of metrics to collect
    - country: Country code (default: us)
    - granularity: Data granularity (DAILY/WEEKLY/MONTHLY, default: MONTHLY)
    - start_date: Start date in YYYY-MM-DD format (optional)
    - end_date: End date in YYYY-MM-DD format (optional)
    
    Available Fields:
    Traffic & Engagement:
    - all_traffic_visits, desktop_visits, mobile_visits
    - all_page_views, desktop_page_views, mobile_page_views
    - all_traffic_pages_per_visit, desktop_pages_per_visit, mobile_pages_per_visit
    - all_traffic_average_visit_duration, desktop_average_visit_duration, mobile_average_visit_duration
    - all_traffic_bounce_rate, desktop_bounce_rate, mobile_bounce_rate
    - desktop_unique_visitors, mobile_unique_visitors, deduplicated_audience
    - desktop_share, mobile_share
    - desktop_ppc_spend_usd, mobile_ppc_spend_usd
    - desktop_new_visitors, desktop_returning_visitors
    
    Marketing Channels:
    - desktop_marketing_channels_visits, mobile_marketing_channels_visits
    - desktop_marketing_channels_share, mobile_marketing_channels_share
    - channel_name
    
    Similar Sites:
    - similarity_score, overlap_score
    
    Website:
    - global_rank, country_rank, category_rank, category
    - site_description, online_revenue, tags
    
    Geographic:
    - desktop_top_geo
    
    Traffic Sources:
    - desktop_traffic_sources, mobile_traffic_sources
    
    Popular Pages (requires subscription):
    - popular_pages_url, popular_pages_traffic_share
    """
    
    if len(sys.argv) < 3:
        print("Error: domain and metrics are required")
        print(help_text)
        sys.exit(1)
        
    # Check for test mode
    is_test_mode = '--test' in sys.argv
    if is_test_mode:
        sys.argv.remove('--test')
        
    # Parse arguments
    domain = sys.argv[1]
    metrics = [m.strip() for m in sys.argv[2].split(",")]
    country = sys.argv[3] if len(sys.argv) > 3 else "us"
    granularity = sys.argv[4] if len(sys.argv) > 4 else "MONTHLY"
    start_date = sys.argv[5] if len(sys.argv) > 5 else None
    end_date = sys.argv[6] if len(sys.argv) > 6 else None
    
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
        metrics=metrics,
        country=country,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date
    )
    
    print(json.dumps(result, indent=2))
