"""
Sellersprite Product Research Data Collector

This script collects product research data from the Sellersprite API and stores it in the database.
The implementation follows these key requirements:

1. API Configuration:
   - Endpoint: https://api.sellersprite.com/v1/product/research
   - Headers:
     - secret-key: Loaded from data.json configuration
     - content-type: application/json;charset=UTF-8

2. Input Parameters:
   - task_id: Required - Links collected data to specific task
   - marketplace: Required - e.g., "US"
   - nodeId: Required - Category node ID
   - size: Optional - Items per page (defaults to 100, max 200)

3. Pagination Logic:
   - Default: page=1, size=100 when size not provided
   - Maximum total ASINs per collection: 2000
   - Maximum size per page: 200
   - Auto-calculation of required pages based on size parameter

4. Data Processing:
   - Parse API response
   - Transform data to match database schema
   - Store in test.seller_spirit_asins table

Implementation Plan:

1. Configuration Management:
   - Load API credentials from data.json
   - Set up database connection

2. Request Management:
   - Build API request with proper headers
   - Handle pagination
   - Implement rate limiting if needed

3. Data Processing:
   - Parse JSON response
   - Transform to match database schema
   - Validate data types

4. Database Operations:
   - Batch insert records
   - Handle potential duplicates
   - Manage transactions

5. Error Handling:
   - API errors (rate limits, auth issues)
   - Network errors
   - Database errors

6. Logging:
   - Track progress
   - Record errors
   - Monitor performance
"""

import json
import math
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from ..function.config import get_sellersprite_config
from ..function.db import get_db_connection, insert_seller_spirit_asin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SellerSpriteCollector:
    """Collector for Sellersprite Product Research API data."""

    def __init__(self):
        """Initialize the collector with configuration."""
        try:
            self.config = get_sellersprite_config()
            self.base_url = self.config['api']['base_url']
            self.headers = {
                'secret-key': self.config['secret_key'],
                'content-type': 'application/json;charset=UTF-8'
            }
        except KeyError as e:
            logger.error(f"Missing configuration key: {e}")
            raise ValueError(f"Configuration error: Missing {e} in config file")
        except Exception as e:
            logger.error(f"Error initializing collector: {e}")
            raise

    def _calculate_pages(self, size: Optional[int] = None) -> tuple[int, int]:
        """Calculate number of pages and items per page based on size parameter."""
        if not size:
            return 1, 100  # Default values

        # Ensure size doesn't exceed maximum total ASINs
        size = min(size, 2000)
        # Calculate optimal page size (max 200 per page)
        page_size = min(200, size)
        # Calculate number of pages needed
        pages = math.ceil(size / page_size)

        logger.info(f"Calculated pagination: {pages} pages with {page_size} items per page")
        return pages, page_size

    def _make_request(self, marketplace: str, node_id: int, page: int,
                     size: int) -> Dict[str, Any]:
        """Make API request to Sellersprite."""
        url = f"{self.base_url}/product/research"
        payload = {
            "marketplace": marketplace,
            "nodeId": node_id,
            "page": page,
            "size": size,
            "order": {
                "field": "bsr_rank",
                "desc": False
            }
        }

        try:
            logger.info(f"Making request to {url} - Page {page}/{size}")
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {e}")
            raise

    def collect_data(self, task_id: int, marketplace: str, node_id: int,
                    size: Optional[int] = None) -> None:
        """
        Collect product research data from Sellersprite API.

        Args:
            task_id: ID of the collection task
            marketplace: Target marketplace (e.g., "US")
            node_id: Category node ID
            size: Optional total number of items to collect (default: 100)
        """
        logger.info(f"Starting data collection - Task ID: {task_id}, "
                   f"Marketplace: {marketplace}, Node ID: {node_id}, Size: {size}")

        pages, page_size = self._calculate_pages(size)
        conn = get_db_connection()
        products_processed = 0

        try:
            for page in range(1, pages + 1):
                data = self._make_request(marketplace, node_id, page, page_size)
                products = data.get('products', [])

                if not products:
                    logger.warning(f"No products found on page {page}")
                    break

                for product in products:
                    try:
                        # Add task_id and ensure required fields
                        product['task_id'] = task_id

                        # Validate required fields
                        if not product.get('asin'):
                            logger.warning(f"Skipping product without ASIN in response")
                            continue

                        # Insert into database
                        insert_seller_spirit_asin(conn, product)
                        products_processed += 1

                    except Exception as e:
                        logger.error(f"Error processing product {product.get('asin', 'unknown')}: {e}")
                        continue

                logger.info(f"Completed page {page}/{pages} - "
                          f"Processed {len(products)} products")

            logger.info(f"Data collection completed - "
                       f"Total products processed: {products_processed}")

        except Exception as e:
            logger.error(f"Error collecting data: {str(e)}")
            raise
        finally:
            conn.close()
            logger.info("Database connection closed")


def collect_seller_sprite_data(task_id: int, marketplace: str, node_id: int,
                             size: Optional[int] = None) -> None:
    """
    Main entry point for collecting Sellersprite product research data.

    Args:
        task_id: ID of the collection task
        marketplace: Target marketplace (e.g., "US")
        node_id: Category node ID
        size: Optional total number of items to collect (default: 100)
    """
    try:
        collector = SellerSpriteCollector()
        collector.collect_data(task_id, marketplace, node_id, size)
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        raise

if __name__ == "__main__":
    # Example usage
    try:
        collect_seller_sprite_data(
            task_id=1,
            marketplace="US",
            node_id=3168061,
            size=100
        )
    except Exception as e:
        logger.error(f"Script execution failed: {e}")
        raise
