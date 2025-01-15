-- Create table for SimilarWeb Websites Dataset ODS
CREATE TABLE IF NOT EXISTS test.similarweb_website_traffic_engagement (
    -- Primary Keys and Identifiers
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    country VARCHAR(2) NOT NULL,
    date_month DATE NOT NULL,
    granularity ENUM('DAILY', 'WEEKLY', 'MONTHLY') NOT NULL,

    -- Traffic & Engagement Table Fields
    -- Visits
    all_traffic_visits DOUBLE,
    desktop_visits DOUBLE,
    mobile_visits DOUBLE,

    -- Page Views
    all_page_views DOUBLE,
    desktop_page_views DOUBLE,
    mobile_page_views DOUBLE,

    -- Pages per Visit
    all_traffic_pages_per_visit DOUBLE,
    desktop_pages_per_visit DOUBLE,
    mobile_pages_per_visit DOUBLE,

    -- Visit Duration
    all_traffic_average_visit_duration DOUBLE,
    desktop_average_visit_duration DOUBLE,
    mobile_average_visit_duration DOUBLE,

    -- Bounce Rate
    all_traffic_bounce_rate DOUBLE,
    desktop_bounce_rate DOUBLE,
    mobile_bounce_rate DOUBLE,

    -- Unique Visitors
    desktop_unique_visitors DOUBLE,
    mobile_unique_visitors DOUBLE,
    deduplicated_audience DOUBLE,

    -- Traffic Share
    desktop_share DOUBLE,
    mobile_share DOUBLE,

    -- PPC Spend
    desktop_ppc_spend_usd DOUBLE,
    mobile_ppc_spend_usd DOUBLE,

    -- Visitor Types
    desktop_new_visitors DOUBLE,
    desktop_returning_visitors DOUBLE,

    -- Rankings
    global_rank INT,
    country_rank INT,
    category_rank_new INT,
    category VARCHAR(255),

    -- Marketing Channels Table Fields
    desktop_marketing_channels_visits DOUBLE,
    mobile_marketing_channels_visits DOUBLE,
    desktop_marketing_channels_share DOUBLE,
    mobile_marketing_channels_share DOUBLE,
    channel_name VARCHAR(50),
    marketing_channels_data JSON,  -- Stores full marketing channels breakdown

    -- Similar Sites Table Fields
    similar_sites_data JSON,  -- Stores array of similar sites with affinity scores

    -- Website Table Fields
    site_description JSON,  -- Stores website description data
    online_revenue JSON,    -- Stores revenue estimates
    category_rank JSON,     -- Stores category rank data
    tags JSON,             -- Stores website tags

    -- Desktop Top Geo Table Fields
    desktop_top_geo JSON,   -- Stores geographical traffic distribution

    -- Traffic Sources Table Fields
    desktop_traffic_sources JSON,  -- Stores traffic sources breakdown
    mobile_traffic_sources JSON,   -- Stores mobile traffic sources breakdown

    -- Metadata and Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_task_id (task_id),
    INDEX idx_domain_country (domain, country),
    INDEX idx_date (date_month),
    INDEX idx_domain_date (domain, date_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Comments explaining the table structure
COMMENT ON TABLE test.similarweb_website_traffic_engagement IS 'ODS table for SimilarWeb Websites Dataset combining all 6 sub-tables';
