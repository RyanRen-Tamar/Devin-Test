# LAMTA Ad Performance Analysis

## 项目概述 (Project Overview)
LAMTA广告效果分析工具是一个用于分析和可视化广告活动性能的Python应用程序。该工具提供了详细的预算使用分析、ROI跟踪和交互式数据可视化功能。

## 核心功能 (Core Features)
- 广告活动数据分析和性能评估
- 预算使用情况监控和优化建议
- 交互式ECharts数据可视化
- 多维度KPI指标分析
- 中文分析报告生成

## 项目结构 (Project Structure)
```
.
├── README.md                      # 项目文档
├── analysis.py                    # 核心分析脚本
├── analysis_report.md             # 分析报告输出
├── scripts/
│   └── generate_charts_echarts.py # ECharts图表生成脚本
└── visualization/
    ├── spend_ratio_chart.html     # 预算使用率可视化界面
    ├── spend_sales_chart.html     # 支出销售对比可视化界面
    ├── spend_ratio_echarts.json   # 预算使用率数据配置
    └── spend_sales_echarts.json   # 支出销售对比数据配置
```

## 使用说明 (Usage Instructions)
1. 运行分析脚本：
```bash
python analysis.py
```

2. 查看分析报告：
- 打开 `analysis_report.md` 查看详细分析结果
- 通过浏览器打开 HTML 文件查看交互式图表：
  - `spend_ratio_chart.html`: 预算使用率趋势图
  - `spend_sales_chart.html`: 支出与销售额关系图

## 数据格式 (Data Format)
分析脚本支持以下数据结构：
```python
{
  "ad_performance": [
    {
      "campaign_id": str,
      "campaign_name": str,
      "date": str,
      "spend": float,
      "impressions": int,
      "clicks": int,
      "ad_sales": float,
      ...
    }
  ],
  "listing_info": [...],
  "budget_config": [...]
}
```

## 输出说明 (Output Explanation)
1. 分析报告 (analysis_report.md)：
   - 活动性能概览
   - 预算使用分析
   - KPI指标评估
   - 优化建议

2. 可视化图表：
   - 预算使用率趋势
   - 支出与销售额关系分析
   - 交互式数据展示
   - 趋势线分析

## 开发说明 (Development Notes)
- Python 3.12+ 环境
- 依赖包：pandas, numpy
- 使用ECharts进行数据可视化
- 支持中文输出和报告生成

## 注意事项 (Notes)
- 所有输出文件会自动生成在项目根目录
- 图表配置文件使用UTF-8编码以支持中文
- 建议使用现代浏览器查看可视化内容
