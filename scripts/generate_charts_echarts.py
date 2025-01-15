import json
import pandas as pd
import numpy as np
from typing import Dict, Any

def generate_daily_spend_ratio_echarts(df: pd.DataFrame) -> str:
    """
    生成每日预算使用率趋势图的 ECharts 配置
    
    Args:
        df: 包含广告数据的 DataFrame，需要包含 date, campaign_name, daily_spend_ratio 列
    
    Returns:
        str: ECharts 配置的 JSON 字符串
    """
    # 按活动名称和日期分组，确保数据正确排序
    df['date'] = pd.to_datetime(df['date'])
    dates = df['date'].dt.strftime('%Y-%m-%d').unique().tolist()
    campaigns = df['campaign_name'].unique().tolist()
    
    # 为每个活动准备数据系列
    series_data = []
    for campaign in campaigns:
        campaign_data = df[df['campaign_name'] == campaign]
        data = campaign_data.set_index('date')['daily_spend_ratio'].reindex(
            pd.to_datetime(dates)
        ).tolist()
        series_data.append({
            "name": campaign,
            "type": "line",
            "data": data,
            "connectNulls": True,  # 跳过空值，保持线条连续
            "emphasis": {
                "focus": "series"
            },
            "markPoint": {
                "data": [
                    {"type": "max", "name": "最高值"},
                    {"type": "min", "name": "最低值"}
                ]
            }
        })
    
    option = {
        "title": {
            "text": "每日预算使用率趋势",
            "left": "center"
        },
        "tooltip": {
            "trigger": "axis",
            "formatter": "{b}<br/>{a}: {c}%"
        },
        "legend": {
            "data": campaigns,
            "top": "30px"
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "category",
            "data": dates,
            "boundaryGap": False
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {
                "formatter": "{value}%"
            }
        },
        "series": series_data,
        "toolbox": {
            "feature": {
                "dataZoom": {},
                "restore": {},
                "saveAsImage": {}
            }
        }
    }
    
    return json.dumps(option, ensure_ascii=False, indent=2)

def generate_spend_vs_sales_echarts(df: pd.DataFrame) -> str:
    """
    生成支出与销售额对比的散点图 ECharts 配置
    
    Args:
        df: 包含广告数据的 DataFrame，需要包含 campaign_name, spend, ad_sales 列
    
    Returns:
        str: ECharts 配置的 JSON 字符串
    """
    # 按活动准备数据系列
    series_data = []
    campaigns = df['campaign_name'].unique().tolist()
    
    for campaign in campaigns:
        campaign_data = df[df['campaign_name'] == campaign]
        data = [[float(s), float(a)] for s, a in zip(
            campaign_data['spend'].fillna(0),
            campaign_data['ad_sales'].fillna(0)
        ) if pd.notna(s) and pd.notna(a)]
        
        series_data.append({
            "name": campaign,
            "type": "scatter",
            "data": data,
            "emphasis": {
                "focus": "series",
                "label": {
                    "show": True,
                    "formatter": "function(param) { return '支出: ' + param.value[0].toFixed(2) + '\\n销售额: ' + param.value[1].toFixed(2); }"
                }
            }
        })
    
    option = {
        "title": {
            "text": "广告支出与销售额关系",
            "left": "center"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "function(param) { return param.seriesName + '<br/>' + '支出: ' + param.value[0].toFixed(2) + '<br/>' + '销售额: ' + param.value[1].toFixed(2); }"
        },
        "legend": {
            "data": campaigns,
            "top": "30px"
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "日均支出",
            "nameLocation": "center",
            "nameGap": 30
        },
        "yAxis": {
            "type": "value",
            "name": "销售额",
            "nameLocation": "center",
            "nameGap": 30
        },
        "series": series_data,
        "toolbox": {
            "feature": {
                "dataZoom": {},
                "restore": {},
                "saveAsImage": {}
            }
        }
    }
    
    return json.dumps(option, ensure_ascii=False, indent=2)

def add_trend_line(option: Dict[str, Any]) -> Dict[str, Any]:
    """
    为散点图添加趋势线
    
    Args:
        option: ECharts 配置字典
    
    Returns:
        Dict[str, Any]: 更新后的配置字典
    """
    try:
        # 为每个散点图系列添加对应的趋势线
        original_series_count = len(option.get("series", []))
        trend_series = []
        
        for i in range(original_series_count):
            series = option["series"][i]
            if series.get("type") != "scatter":
                continue
                
            scatter_data = series.get("data", [])
            if len(scatter_data) < 2:
                continue
                
            # 计算线性回归
            x_values = [point[0] for point in scatter_data if isinstance(point, (list, tuple)) and len(point) >= 2]
            y_values = [point[1] for point in scatter_data if isinstance(point, (list, tuple)) and len(point) >= 2]
            
            if len(x_values) < 2:
                continue
                
            try:
                coeffs = np.polyfit(x_values, y_values, 1)
                trend_line = np.poly1d(coeffs)
                
                # 添加趋势线系列
                x_range = [min(x_values), max(x_values)]
                trend_data = [[x, float(trend_line(x))] for x in x_range]
                
                trend_series.append({
                    "name": f"{series.get('name', f'系列 {i+1}')} 趋势线",
                    "type": "line",
                    "data": trend_data,
                    "showSymbol": False,
                    "lineStyle": {
                        "type": "dashed"
                    }
                })
            except (ValueError, np.linalg.LinAlgError):
                continue
        
        option["series"].extend(trend_series)
        return option
    except Exception as e:
        print(f"添加趋势线时发生错误: {str(e)}")
        return option  # 返回原始配置

if __name__ == "__main__":
    try:
        # 测试数据
        test_data = {
            "date": ["2025-05-01", "2025-05-02", "2025-05-03"],
            "campaign_name": ["SummerSale", "SummerSale", "MegaDeal"],
            "daily_spend_ratio": [0.8, 0.9, None],
            "spend": [100, 150, None],
            "ad_sales": [200, 300, 250]
        }
        test_df = pd.DataFrame(test_data)
        
        # 测试生成图表配置
        print("正在生成每日预算使用率趋势图配置...")
        spend_ratio_config = generate_daily_spend_ratio_echarts(test_df)
        print("每日预算使用率趋势图配置已生成")
        
        print("\n正在生成支出与销售额对比图配置...")
        spend_sales_config = generate_spend_vs_sales_echarts(test_df)
        print("支出与销售额对比图配置已生成")
        
        # 保存测试配置到文件
        with open("test_spend_ratio_chart.json", "w", encoding="utf-8") as f:
            f.write(spend_ratio_config)
        with open("test_spend_sales_chart.json", "w", encoding="utf-8") as f:
            f.write(spend_sales_config)
            
        print("\n配置文件已保存。可以通过以下文件查看：")
        print("- test_spend_ratio_chart.json")
        print("- test_spend_sales_chart.json")
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
