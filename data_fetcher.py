import os
import logging
from typing import Optional, Dict, Any
from unittest.mock import MagicMock

logger = logging.getLogger(__name__)

# Global mock for testing
_mock_connection = None

def set_mock_connection(mock_conn):
    """Set mock connection for testing"""
    global _mock_connection
    _mock_connection = mock_conn

def create_connection():
    """Create database connection or return mock for testing"""
    global _mock_connection
    if _mock_connection is not None:
        return _mock_connection
        
    try:
        # In production, this would use real pymysql
        # For testing, we'll always use the mock
        raise ImportError("Database connection not available in test environment")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

######################################################
# 1. 根据用户上传的 ASIN 列表，在 saas.customer_asin 表中
#    判断哪些是父ASIN、哪些是子ASIN，并获取最终要查询的子ASIN集合
######################################################
def fetch_asin_hierarchy(user_asin_list):
    """
    给定用户上传的一批ASIN, 在 saas.customer_asin 表中查询:
      - 如果某 ASIN 是父ASIN, 看它有哪些子ASIN
      - 如果某 ASIN 是子ASIN, 找到它的父ASIN
    最终返回一个字典，key是父ASIN，value是子ASIN列表（已去重）
    只返回 sku_status 包含 1 的ASIN
    """
    if not user_asin_list:
        return {}

    conn = create_connection()
    try:
        with conn.cursor() as cur:
            # 结果处理
            result_dict = {}
            
            # 处理每个ASIN
            for asin in user_asin_list:
                # 查询作为父ASIN的情况
                cur.execute(
                    "SELECT pasin as parent_asin, asin_id as child_asin "
                    "FROM saas.customer_asin "
                    "WHERE pasin = %s "
                    "AND CAST(sku_status AS JSON) LIKE %s",
                    (asin, '%1%')
                )
                parent_rows = cur.fetchall()
                
                # 查询作为子ASIN的情况
                cur.execute(
                    "SELECT pasin as parent_asin, asin_id as child_asin "
                    "FROM saas.customer_asin "
                    "WHERE asin_id = %s "
                    "AND CAST(sku_status AS JSON) LIKE %s",
                    (asin, '%1%')
                )
                child_rows = cur.fetchall()
                
                # 处理parent_rows
                for row in parent_rows:
                    p_asin = row["parent_asin"]
                    c_asin = row["child_asin"]
                    if p_asin not in result_dict:
                        result_dict[p_asin] = set()
                    if c_asin:
                        result_dict[p_asin].add(c_asin)
                
                # 处理child_rows
                for row in child_rows:
                    p_asin = row["parent_asin"]
                    c_asin = row["child_asin"]
                    if p_asin not in result_dict:
                        result_dict[p_asin] = set()
                    result_dict[p_asin].add(c_asin)
                
                # 如果既不是父也不是子，检查是否为独立ASIN
                if not parent_rows and not child_rows:
                    cur.execute(
                        "SELECT 1 "
                        "FROM saas.customer_asin "
                        "WHERE (pasin = %s OR asin_id = %s) "
                        "AND CAST(sku_status AS JSON) LIKE %s "
                        "LIMIT 1",
                        (asin, asin, '%1%')
                    )
                    if cur.fetchone():  # 只有当sku_status包含1时才添加
                        result_dict[asin] = {asin}
            
            # 最后将所有集合转换为排序后的列表
            return {k: sorted(list(v)) for k, v in result_dict.items()}
    finally:
        conn.close()


###############################
# 2. coupon 信息
###############################
def fetch_coupon_info(asin_list, start_dt=None, end_dt=None):
    """
    按子ASIN来查询优惠券数据:
    asins字段格式为 [{"asin": "B0DJ2W75P8"}]
    """
    if not asin_list:
        return []
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
            SELECT 
                coupon_id, name, website_message,
                start_cus_dt, end_cus_dt, discount_type,
                discount_amount, total_discount, clips,
                redemptions, budget, budget_spent,
                budget_remaining, budget_percentage_used,
                sales, asins
            FROM sp_store_report_get_coupon_performance_report
            WHERE 1=1
            """
            params = []
            
            if start_dt:
                base_sql += " AND start_cus_dt >= %s"
                params.append(start_dt)
            if end_dt:
                base_sql += " AND end_cus_dt <= %s"
                params.append(end_dt)
            
            # 使用 JSON_CONTAINS 函数检查 asins 字段中的 asin
            or_clauses = []
            for asin in asin_list:
                or_clauses.append("JSON_CONTAINS(asins, JSON_OBJECT('asin', %s))")
                params.append(asin)
            
            if or_clauses:
                base_sql += " AND (" + " OR ".join(or_clauses) + ")"
            
            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


###############################
# 3. deal 信息
###############################
def fetch_deal_info(asin_list, start_dt=None, end_dt=None):
    """
    查询 Deal 数据，使用 JSON_CONTAINS 函数来检查 included_products 字段中是否包含指定的 ASIN
    included_products字段格式为:
    [{"asin": "B07KFTV8WM", "productName": "...", "productGlanceViews": 12146, ...}]
    """
    if not asin_list:
        return []
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
            SELECT 
                store_id,
                promotion_id, promotion_name, type,
                start_cus_dt, promo_end_cus_dt, status,
                glance_views, revenue, units_sold,
                included_products
            FROM sp_store_report_get_promotion_performance_report
            WHERE 1=1
            """
            params = []

            if start_dt:
                base_sql += " AND start_cus_dt >= %s"
                params.append(start_dt)
            if end_dt:
                base_sql += " AND promo_end_cus_dt <= %s"  # 修正end_dt的字段名
                params.append(end_dt)

            # 使用 JSON_CONTAINS 函数检查每个 ASIN
            or_clauses = []
            for asin in asin_list:
                or_clauses.append("JSON_CONTAINS(included_products, JSON_OBJECT('asin', %s))")
                params.append(asin)
            
            if or_clauses:
                base_sql += " AND (" + " OR ".join(or_clauses) + ")"
            
            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


###############################
# 4. SC 销量、Session 数据！！！！！！！没有分市场，需要下周再改
###############################
def fetch_sales_sc_data(asin_list, start_date=None, end_date=None):
    """
    查询 SC 数据: bigdata.sp_store_report_flat_file_all_orders_data_by_order_date_general
    - store_id
    - client_id
    - asin
    - cus_date
    - units_ordered
    - ordered_product_sales_amount
    - item_promotion_discount
    """
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
            SELECT store_id, client_id, asin,
                   purchase_cus_time as cus_date,
                   quantity as units_ordered, 
                   item_price as ordered_product_sales_amount,
                   item_promotion_discount
            FROM bigdata.sp_store_report_flat_file_all_orders_data_by_order_date_general
            WHERE order_status != 'Cancelled'
            """
            params = []

            if start_date:
                base_sql += " AND purchase_cus_time >= %s"
                params.append(start_date)
            if end_date:
                base_sql += " AND purchase_cus_time <= %s"
                params.append(end_date)

            # 添加 ASIN 条件
            if asin_list:
                asin_placeholders = ','.join(['%s'] * len(asin_list))
                base_sql += f" AND asin IN ({asin_placeholders})"
                params.extend(asin_list)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


###############################
# 5. VC 销量、session 数据
###############################
def fetch_sales_vc_data(asin_list=None, start_date=None, end_date=None):
    """
    查询 VC 数据:
      - bigdata.sp_store_report_get_vendor_sales
    返回字段:
      - store_id: 店铺ID
      - distributor_view: 分销商视图
      - start_date: 日期
      - asin: 产品ASIN
      - ordered_revenue: 订单收入
      - shipped_cogs: 发货成本
      - shipped_units: 发货数量
      - ordered_units: 订单数量
    """
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
            SELECT store_id, distributor_view, start_date, asin,
                   ordered_revenue, shipped_cogs, shipped_units, ordered_units
            FROM bigdata.sp_store_report_get_vendor_sales
            """
            conditions = []
            params = []

            if asin_list:
                asin_placeholders = ','.join(['%s'] * len(asin_list))
                conditions.append(f"asin IN ({asin_placeholders})")
                params.extend(asin_list)
            if start_date:
                conditions.append("start_date >= %s")
                params.append(start_date)
            if end_date:
                conditions.append("start_date <= %s")
                params.append(end_date)
            
            if conditions:
                base_sql += " WHERE " + " AND ".join(conditions)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


###############################
# 6. 广告数据 (天级)
###############################
def fetch_ad_data(asin_list, start_date=None, end_date=None):
    """
    查询广告数据，从 sp_advertised_product_report 和 sp_campaigns_list 表获取
    返回字段:
      - cus_date: 日期
      - campaign_id: 广告活动ID
      - advertised_asin: 广告ASIN
      - spend: 花费
      - clicks: 点击数
      - impressions: 展示数
      - sales_7d: 7天销售额
      - purchases_7d: 7天订单数
      - units_sold_clicks_7d: 7天销量
      - campaign_name: 广告活动名称
    """
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
            SELECT 
                sapr.cus_date,
                sapr.campaign_id,
                sapr.advertised_asin,
                sapr.spend,
                sapr.clicks,
                sapr.impressions,
                sapr.sales_7d,
                sapr.purchases_7d,
                sapr.units_sold_clicks_7d,
                scl.name AS campaign_name
            FROM bigdata.sp_advertised_product_report sapr
            LEFT JOIN bigdata.sp_campaigns_list scl
                ON sapr.campaign_id = scl.campaign_id
                AND scl.get_date = 
                    CASE
                        WHEN HOUR(CURRENT_TIME()) > 0 THEN CURRENT_DATE()
                        ELSE DATE(DATE_SUB(NOW(), INTERVAL 1 DAY))
                    END
                AND scl.get_hour = 
                    CASE
                        WHEN HOUR(CURRENT_TIME()) > 0 THEN HOUR(CURRENT_TIME()) - 1
                        ELSE HOUR(DATE_SUB(NOW(), INTERVAL 1 HOUR))
                    END
            WHERE 1 = 1
            """
            params = []

            if start_date:
                base_sql += " AND sapr.cus_date >= %s"
                params.append(start_date)
            if end_date:
                base_sql += " AND sapr.cus_date <= %s"
                params.append(end_date)
            
            # 添加 ASIN 条件
            if asin_list:
                asin_placeholders = ','.join(['%s'] * len(asin_list))
                base_sql += f" AND sapr.advertised_asin IN ({asin_placeholders})"
                params.extend(asin_list)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


###############################
# 7. 订单数据 (SC 订单明细) 缺少市场 id 的条件限制，order_status也需要调查
###############################
def fetch_orders_data(asin_list, start_dt=None, end_dt=None):
    """
    查询订单数据: bigdata.sp_store_report_flat_file_all_orders_data_by_order_date_general
    - purchase_date, purchase_cus_time, sales_channel, asin, quantity, item_price, ...
    """
    try:
        conn = create_connection()
        with conn.cursor() as cur:
            base_sql = """
            SELECT purchase_cus_time, sales_channel, asin,
                   quantity, item_price, item_promotion_discount
            FROM  bigdata.sp_store_report_flat_file_all_orders_data_by_order_date_general
            WHERE order_status != 'Cancelled'
            """
            params = []

            if start_dt:
                base_sql += " AND purchase_date >= %s"
                params.append(start_dt)
            if end_dt:
                base_sql += " AND purchase_date <= %s"
                params.append(end_dt)
            
            # 添加 ASIN 条件
            if asin_list:
                asin_placeholders = ','.join(['%s'] * len(asin_list))
                base_sql += f" AND asin IN ({asin_placeholders})"
                params.extend(asin_list)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    except Exception as e:
        print(f"Error fetching orders data: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


###############################
# 8. 历史记录 (campaign_history & ad_group_history)
###############################
def fetch_campaign_history(asin_list, start_ms=None, end_ms=None):
    """
    查询 bigdata.campaign_history
    - campaign_id, change_time(毫秒), change_type, previous_value, new_value, metadata
    """
    try:
        conn = create_connection()
        with conn.cursor() as cur:
            base_sql = """
            SELECT campaign_id, change_time, change_type, previous_value, new_value, metadata
            FROM bigdata.campaign_history
            WHERE 1=1
            """
            params = []

            # 如果需要按毫秒时间范围筛选,可以自行定义change_time >= start_ms
            if start_ms:
                base_sql += " AND change_time >= %s"
                params.append(start_ms)
            if end_ms:
                base_sql += " AND change_time <= %s"
                params.append(end_ms)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    except Exception as e:
        print(f"Error fetching campaign history: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def fetch_adgroup_history(asin_list, start_ms=None, end_ms=None):
    """
    查询 bigdata.ad_group_history
    - campaign_id, change_time(毫秒), change_type, previous_value, new_value, metadata
    """
    try:
        conn = create_connection()
        with conn.cursor() as cur:
            base_sql = """
            SELECT campaign_id, change_time, change_type, previous_value, new_value, metadata
            FROM bigdata.ad_group_history
            WHERE 1=1
            """
            params = []

            if start_ms:
                base_sql += " AND change_time >= %s"
                params.append(start_ms)
            if end_ms:
                base_sql += " AND change_time <= %s"
                params.append(end_ms)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    except Exception as e:
        print(f"Error fetching ad group history: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


###############################
# 9. 广告小时数据 (sp_traffic / sp_conversion)
###############################
def fetch_ad_hourly_traffic(asin_list, start_date=None, end_date=None):
    """
    查询小时级点击/花费等数据: bigdata.sp_traffic
    - store_id, cus_date, campaign_id, ad_id, keyword_id, keyword_text, placement,
      time_window_start, clicks, impressions, cost
    """
    if not asin_list:
        return []
        
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
            SELECT store_id, cus_date, campaign_id, ad_id, keyword_id, keyword_text, placement,
                   time_window_start, clicks, impressions, cost
            FROM sp_traffic
            WHERE campaign_id IN (
                SELECT DISTINCT campaign_id 
                FROM bigdata.sp_advertised_product_report 
                WHERE advertised_asin IN ({})
            )
            """.format(','.join(['%s'] * len(asin_list)))
            
            params = asin_list.copy()

            if start_date:
                base_sql += " AND cus_date >= %s"
                params.append(start_date)
            if end_date:
                base_sql += " AND cus_date <= %s"
                params.append(end_date)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


def fetch_ad_hourly_conversion(asin_list, start_date=None, end_date=None):
    """
    查询小时级归因订单/销售数据: bigdata.sp_conversion
    - store_id, cus_date, campaign_id, ad_id, keyword_id, keyword_text, placement,
      time_window_start, attributed_conversions_7d, attributed_sales_7d, ...
    """
    if not asin_list:
        return []
        
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
            SELECT store_id, cus_date, campaign_id, ad_id, keyword_id, keyword_text, placement,
                   time_window_start,
                   attributed_conversions_7d, attributed_sales_7d, attributed_units_ordered_7d
            FROM sp_conversion
            WHERE campaign_id IN (
                SELECT DISTINCT campaign_id 
                FROM bigdata.sp_advertised_product_report 
                WHERE advertised_asin IN ({})
            )
            """.format(','.join(['%s'] * len(asin_list)))
            
            params = asin_list.copy()

            if start_date:
                base_sql += " AND cus_date >= %s"
                params.append(start_date)
            if end_date:
                base_sql += " AND cus_date <= %s"
                params.append(end_date)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


###############################
# 10. 库存数据
###############################
def fetch_inventory_data(asin_list):
    """
    查询库存: bigdata.sp_fba_inventory_item
    - store_id, asin, seller_sku, last_updated_time, total_quantity
    """
    if not asin_list:
        return []
        
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            sql_str = """
            SELECT store_id, granularity_id, asin, seller_sku, condition, last_updated_time, total_quantity
            FROM sp_fba_inventory_item
            WHERE 1=1
            """
            params = []
            
            # 添加 ASIN 条件
            if asin_list:
                asin_placeholders = ','.join(['%s'] * len(asin_list))
                sql_str += f" AND asin IN ({asin_placeholders})"
                params.extend(asin_list)

            cur.execute(sql_str, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


def fetch_campaign_report(asin_list, start_date=None, end_date=None):
    """
    查询广告活动报告数据: bigdata.sp_campaign_report
    """
    conn = create_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
            SELECT 
                scr.store_id, scr.cus_date, scr.campaign_id,
                scl.name as campaign_name,
                scr.spend, 
                scr.clicks, scr.impressions,
                scr.sales7d, scr.purchases_7d, scr.units_sold_clicks_7d
            FROM sp_campaign_report scr
            INNER JOIN (
                SELECT DISTINCT campaign_id
                FROM bigdata.sp_advertised_product_report
                WHERE advertised_asin IN ({})
            ) sapr ON scr.campaign_id = sapr.campaign_id
            LEFT JOIN bigdata.sp_campaigns_list scl
                ON scr.campaign_id = scl.campaign_id
                AND scl.get_date = 
                    CASE
                        WHEN HOUR(CURRENT_TIME()) > 0 THEN CURRENT_DATE()
                        ELSE DATE(DATE_SUB(NOW(), INTERVAL 1 DAY))
                    END
                AND scl.get_hour = 
                    CASE
                        WHEN HOUR(CURRENT_TIME()) > 0 THEN HOUR(CURRENT_TIME()) - 1
                        ELSE HOUR(DATE_SUB(NOW(), INTERVAL 1 HOUR))
                    END
            WHERE 1=1
            """.format(','.join(['%s'] * len(asin_list)))
            
            params = asin_list.copy()

            if start_date:
                base_sql += " AND scr.cus_date >= %s"
                params.append(start_date)
            if end_date:
                base_sql += " AND scr.cus_date <= %s"
                params.append(end_date)

            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


###session 数据（代补充）
###
