"""Database connection and utilities for amazondata project."""
import mysql.connector
from typing import Dict, Any

def get_db_connection():
    """Get MySQL database connection.

    Note: Connection parameters should be configured via environment variables
    or a separate configuration mechanism for security.
    """
    # TODO: Replace with actual connection parameters
    return mysql.connector.connect(
        host="localhost",
        user="user",
        password="password",
        database="test"
    )

def insert_seller_spirit_asin(conn, data: Dict[str, Any]):
    """Insert data into seller_spirit_asins table."""
    cursor = conn.cursor()

    columns = [
        'task_id', 'asin', 'brand', 'brandUrl', 'imageUrl', 'title',
        'parent', 'nodeId', 'nodeIdPath', 'nodeLabelPath', 'bsrId',
        'bsr', 'bsrCr', 'bsrCv', 'amzUnit', 'amzUnitDate', 'amzSales',
        'units', 'unitsGr', 'revenue', 'price', 'averagePrice',
        'primePrice', 'profit', 'fba', 'ratings', 'ratingsRate',
        'rating', 'ratingsCv', 'ratingDelta', 'lqs', 'availableDate',
        'fulfillment', 'variations', 'sellers', 'sellerId', 'sellerName',
        'sellerNation', 'badge', 'weight', 'dimension', 'dimensionsType',
        'sku', 'deliveryPrice', 'subcategories'
    ]

    placeholders = ', '.join(['%s'] * len(columns))
    query = f"""
        INSERT INTO seller_spirit_asins
        ({', '.join(columns)})
        VALUES ({placeholders})
    """

    values = [data.get(col) for col in columns]
    cursor.execute(query, values)
    conn.commit()
    cursor.close()
