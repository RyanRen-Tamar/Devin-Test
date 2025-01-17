"""SimilarWeb API configuration"""
from typing import Dict, List, Set

# SimilarWeb metrics configuration
SIMILARWEB_METRICS = {
    "traffic_and_engagement": [
        "all_traffic_visits",
        "desktop_visits",
        "mobile_visits",
        "all_page_views",
        "desktop_page_views",
        "mobile_page_views",
        "all_traffic_pages_per_visit",
        "desktop_pages_per_visit",
        "mobile_pages_per_visit",
        "all_traffic_average_visit_duration",
        "desktop_average_visit_duration",
        "mobile_average_visit_duration",
        "all_traffic_bounce_rate",
        "desktop_bounce_rate",
        "mobile_bounce_rate",
        "desktop_unique_visitors",
        "mobile_unique_visitors",
        "deduplicated_audience",
        "desktop_share",
        "mobile_share",
        "desktop_ppc_spend_usd",
        "mobile_ppc_spend_usd",
        "desktop_new_visitors",
        "desktop_returning_visitors"
    ],
    "marketing_channels": [
        "desktop_marketing_channels_visits",
        "mobile_marketing_channels_visits",
        "desktop_marketing_channels_share",
        "mobile_marketing_channels_share",
        "channel_name"
    ],
    "similar_sites": [
        "similarity_score",
        "overlap_score"
    ],
    "website": [
        "global_rank",
        "country_rank",
        "category_rank",
        "category",
        "site_description",
        "online_revenue",
        "tags"
    ],
    "desktop_top_geo": [
        "desktop_top_geo"
    ],
    "traffic_sources": [
        "desktop_traffic_sources",
        "mobile_traffic_sources"
    ],
    "popular_pages": [
        "popular_pages_url",
        "popular_pages_traffic_share"
    ]
}

# Granularity support for each metric
METRIC_GRANULARITY = {
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

def get_field_to_table_map() -> Dict[str, str]:
    """Get mapping of fields to their respective tables
    
    Returns:
        Dict mapping field names to table names
    """
    field_to_table = {}
    for table, fields in SIMILARWEB_METRICS.items():
        for field in fields:
            field_to_table[field] = table
    return field_to_table

def validate_metrics(metrics: List[str], granularity: str = "MONTHLY") -> None:
    """Validate metrics and their granularity support
    
    Args:
        metrics: List of metrics to validate
        granularity: Data granularity (DAILY/WEEKLY/MONTHLY)
        
    Raises:
        ValueError: If any metric is invalid or unsupported for the given granularity
    """
    if not metrics:
        raise ValueError("metrics parameter is required")
        
    # Validate metrics exist
    all_metrics = set()
    for fields in SIMILARWEB_METRICS.values():
        all_metrics.update(fields)
    
    invalid_metrics = [m for m in metrics if m not in all_metrics]
    if invalid_metrics:
        raise ValueError(f"Invalid metrics: {invalid_metrics}. "
                      f"Valid metrics are: {sorted(all_metrics)}")
    
    # Validate granularity support
    for metric in metrics:
        supported_granularities = METRIC_GRANULARITY[metric]
        if granularity not in supported_granularities:
            raise ValueError(f"Granularity {granularity} not supported for metric {metric}. "
                          f"Supported granularities are: {supported_granularities}")
