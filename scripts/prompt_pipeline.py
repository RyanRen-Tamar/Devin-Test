"""Prompt pipeline for LAMTA's Ad Performance Monitoring using LangGraph architecture."""

import json
import os
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize LLM
llm = ChatOpenAI(
    model="chatgpt-4o-latest",
    temperature=0.1
)

class State(TypedDict):
    initial_analysis: Dict[str, Any]
    cleaned_analysis: Dict[str, Any]
    anomaly_report: Dict[str, Any]
    draft_report: str
    final_report: str
    adjustment_plan: Dict[str, Any]

def load_initial_analysis(state: State) -> State:
    """Load initial analysis from JSON file."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    
    with open(os.path.join(data_dir, "initial_analysis.json"), "r") as f:
        state["initial_analysis"] = json.load(f)
    
    return state

def check_data_completeness(state: State) -> State:
    """Prompt 1: Check data completeness and handle missing values."""
    system_prompt = """You are an AI data analyst specializing in Amazon advertising data analysis.
Your task is to check data completeness and handle missing values in the campaign metrics data.

IMPORTANT: You must respond with ONLY valid JSON that matches the input structure exactly.
Do not include any explanatory text, markdown formatting, or other content.

For each campaign:
1. Verify all required fields are present and valid
2. Fill missing values with historical averages if available
3. Set missing_data_flag=true if values cannot be filled"""

    human_prompt = f"""请分析以下广告系列数据的完整性 (Please analyze this campaign data for completeness):

{json.dumps(state["initial_analysis"], indent=2)}

要求 (Requirements):
1. 验证所有必需字段是否存在且有效 (Verify all required fields)
2. 使用历史平均值填充缺失值 (Fill missing values with historical averages)
3. 无法填充时标记 missing_data_flag=true (Mark unfillable data)

必须仅输出与输入结构完全相同的 JSON。
(Must output JSON matching the input structure exactly.)"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    # Try to get valid JSON response with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            # Clean up response to extract JSON
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            cleaned_analysis = json.loads(content)
            
            # Validate response structure matches input
            if not all(key in cleaned_analysis for key in ["campaigns", "global_stats"]):
                raise ValueError("Response missing required top-level keys")
            
            state["cleaned_analysis"] = cleaned_analysis
            break
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed to get valid JSON after {max_retries} attempts. Error: {str(e)}")
            continue
    
    # Save cleaned analysis
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    with open(os.path.join(data_dir, "cleaned_analysis.json"), "w") as f:
        json.dump(state["cleaned_analysis"], f, indent=2)
    
    return state

def detect_anomalies(state: State) -> State:
    """Prompt 2: Detect anomalies and summarize key findings."""
    system_prompt = """You are an AI analyst specializing in Amazon advertising performance analysis.
Your task is to detect anomalies and patterns in the campaign data.

IMPORTANT: You must respond with ONLY valid JSON matching this exact structure:
{
    "detailed_findings": [
        {
            "campaign_id": "string",
            "type": "budget|roi|inventory|historical",
            "severity": "high|medium|low",
            "description": "string (bilingual zh-CN/en-US)",
            "metrics": {
                "current_value": number,
                "threshold": number,
                "deviation_percentage": number
            }
        }
    ],
    "analysis_summary": {
        "total_anomalies": number,
        "critical_issues": ["string (bilingual zh-CN/en-US)"],
        "recommendations": ["string (bilingual zh-CN/en-US)"]
    }
}"""

    human_prompt = f"""请分析以下清理后的广告系列数据中的异常情况 (Please analyze this cleaned campaign data for anomalies):

{json.dumps(state["cleaned_analysis"], indent=2)}

重点关注 (Focus on):
1. 预算使用情况 (Budget utilization)
   - 超支 (Over-spending)
   - 支出不足 (Under-spending)
2. ROI 和 ACOS 表现 (ROI and ACOS performance)
   - 是否达到目标 (Meeting targets)
   - 显著偏差 (Significant deviations)
3. 库存状态 (Inventory status)
   - 库存风险 (Stock risks)
   - 补货建议 (Restock recommendations)
4. 历史数据对比 (Historical comparison)
   - 异常趋势 (Unusual trends)
   - 季节性因素 (Seasonal factors)

必须仅输出符合指定 JSON 结构的响应。
(Must output JSON response matching the specified structure exactly.)"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    # Try to get valid JSON response with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            # Clean up response to extract JSON
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            anomaly_report = json.loads(content)
            
            # Validate response structure
            required_keys = ["detailed_findings", "analysis_summary"]
            if not all(key in anomaly_report for key in required_keys):
                raise ValueError("Response missing required top-level keys")
            
            # Validate detailed_findings structure
            for finding in anomaly_report["detailed_findings"]:
                required_finding_keys = ["campaign_id", "type", "severity", "description", "metrics"]
                if not all(key in finding for key in required_finding_keys):
                    raise ValueError("Finding missing required keys")
            
            state["anomaly_report"] = anomaly_report
            break
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed to get valid JSON after {max_retries} attempts. Error: {str(e)}")
            continue
    
    # Save anomaly report
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    with open(os.path.join(data_dir, "anomaly_report.json"), "w") as f:
        json.dump(state["anomaly_report"], f, indent=2)
    
    return state

def generate_draft_report(state: State) -> State:
    """Prompt 3: Generate natural language report draft."""
    system_prompt = """You are an AI report writer specializing in Amazon advertising performance reports.
Your task is to create a clear, bilingual (Chinese/English) draft report for operations teams.

IMPORTANT: Your response must be in markdown format with the following structure:
# 广告效果分析报告 (Ad Performance Analysis Report)

## 整体表现概述 (Performance Overview)
[Bilingual summary of overall performance]

## 关键发现 (Key Findings)
### 预算异常 (Budget Anomalies)
[Bilingual details about budget issues]

### ROI 和 ACOS 分析 (ROI and ACOS Analysis)
[Bilingual analysis of ROI/ACOS performance]

### 库存状况 (Inventory Status)
[Bilingual inventory analysis]

## 影响评估 (Impact Assessment)
[Bilingual assessment of business impact]

## 建议行动 (Recommended Actions)
[Bilingual list of suggested actions]"""

    human_prompt = f"""请基于以下异常分析生成双语报告草稿 (Please create a bilingual report draft based on this anomaly analysis):

{json.dumps(state["anomaly_report"], indent=2)}

要求 (Requirements):
1. 总结整体表现 (Summarize overall performance)
2. 突出关键问题 (Highlight key issues)
3. 分析潜在影响 (Analyze potential impacts)
4. 提出初步建议 (Suggest preliminary actions)

注意 (Note):
- 使用清晰专业的语言 (Use clear, professional language)
- 每个部分都需要中英文对照 (Each section must be bilingual)
- 保持markdown格式 (Maintain markdown formatting)"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    # Try to get valid markdown response with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            content = response.content.strip()
            
            # Validate markdown structure
            required_sections = [
                "# 广告效果分析报告",
                "## 整体表现概述",
                "## 关键发现",
                "## 影响评估",
                "## 建议行动"
            ]
            
            if not all(section in content for section in required_sections):
                raise ValueError("Response missing required markdown sections")
            
            state["draft_report"] = content
            break
        except ValueError as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed to get valid markdown after {max_retries} attempts. Error: {str(e)}")
            continue
    
    # Save draft report
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    with open(os.path.join(data_dir, "draft_report.md"), "w") as f:
        f.write(state["draft_report"])
    
    return state

def generate_final_report(state: State) -> State:
    """Prompt 4: Generate final report with charts and action plan."""
    system_prompt = """You are an AI report finalizer specializing in Amazon advertising performance reports.
Your task is to create a polished, bilingual final report with charts and visualizations.

IMPORTANT: Your response must be in markdown format with the following structure:
# 亚马逊广告效果分析报告 (Amazon Advertising Performance Report)

## 执行摘要 (Executive Summary)
[Bilingual executive summary]

## 详细分析 (Detailed Analysis)

### 预算表现 (Budget Performance)
[Bilingual analysis]

<!-- Chart 1: Budget Utilization -->
```chart
{
  "type": "bar",
  "data": {
    "labels": ["Campaign A", "Campaign B"],
    "datasets": [
      {
        "label": "Budget Utilization %",
        "data": [85, 95]
      }
    ]
  }
}
```

### ROI 和 ACOS 分析 (ROI and ACOS Analysis)
[Bilingual analysis]

<!-- Chart 2: ROI & ACOS Trends -->
```chart
{
  "type": "line",
  "data": {
    "labels": ["Day 1", "Day 2", "Day 3"],
    "datasets": [
      {
        "label": "ROI",
        "data": [1.9, 1.75]
      },
      {
        "label": "ACOS",
        "data": [30.0, 36.4]
      }
    ]
  }
}
```

### 库存状况 (Inventory Status)
[Bilingual analysis]

<!-- Chart 3: Inventory Days Left -->
```chart
{
  "type": "gauge",
  "data": {
    "value": 15,
    "min": 0,
    "max": 30,
    "threshold": 7
  }
}
```

## 行动计划 (Action Plan)
[Bilingual action items]

## 后续步骤 (Next Steps)
[Bilingual recommendations]"""

    human_prompt = f"""请基于以下草稿报告和异常分析生成最终报告 (Please generate final report based on this draft and analysis):

草稿报告 (Draft Report):
{state["draft_report"]}

异常分析 (Anomaly Analysis):
{json.dumps(state["anomaly_report"], indent=2)}

要求 (Requirements):
1. 保持双语内容 (Maintain bilingual content)
2. 添加数据可视化 (Add data visualizations)
3. 明确行动计划 (Clear action plan)
4. 具体后续建议 (Specific next steps)

注意 (Note):
- 使用提供的图表模板 (Use provided chart templates)
- 确保数据准确性 (Ensure data accuracy)
- 保持专业性 (Maintain professionalism)"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    # Try to get valid markdown response with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            content = response.content.strip()
            
            # Validate markdown structure
            required_sections = [
                "# 亚马逊广告效果分析报告",
                "## 执行摘要",
                "## 详细分析",
                "### 预算表现",
                "### ROI 和 ACOS 分析",
                "### 库存状况",
                "## 行动计划",
                "## 后续步骤"
            ]
            
            if not all(section in content for section in required_sections):
                raise ValueError("Response missing required markdown sections")
            
            # Validate chart placeholders
            required_charts = [
                "```chart",
                '"type": "bar"',
                '"type": "line"',
                '"type": "gauge"'
            ]
            
            if not all(chart in content for chart in required_charts):
                raise ValueError("Response missing required chart configurations")
            
            state["final_report"] = content
            break
        except ValueError as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed to get valid markdown after {max_retries} attempts. Error: {str(e)}")
            continue
    
    # Save final report
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    with open(os.path.join(data_dir, "final_report.md"), "w") as f:
        f.write(state["final_report"])
    
    return state

def suggest_adjustments(state: State) -> State:
    """Prompt 5: Suggest budget and CPC adjustments."""
    system_prompt = """You are an AI optimization specialist for Amazon advertising campaigns.
Your task is to suggest specific budget and CPC adjustments based on performance data.

IMPORTANT: You must respond with ONLY valid JSON matching this exact structure:
{
    "campaign_adjustments": [
        {
            "campaign_id": "string",
            "campaign_name": "string",
            "budget_adjustment": {
                "action": "increase|decrease|maintain",
                "percentage": number,
                "reason_zh": "string",
                "reason_en": "string"
            },
            "cpc_adjustment": {
                "action": "increase|decrease|maintain",
                "percentage": number,
                "reason_zh": "string",
                "reason_en": "string"
            },
            "timing": {
                "recommended_date": "YYYY-MM-DD",
                "urgency": "high|medium|low"
            }
        }
    ],
    "global_recommendations": {
        "overall_strategy_zh": "string",
        "overall_strategy_en": "string",
        "expected_impacts": [
            {
                "metric": "string",
                "expected_change_zh": "string",
                "expected_change_en": "string",
                "confidence": "high|medium|low"
            }
        ]
    }
}"""

    human_prompt = f"""请基于以下分析和报告提供预算调整建议 (Please provide budget adjustment suggestions based on this analysis and report):

异常分析 (Anomaly Analysis):
{json.dumps(state["anomaly_report"], indent=2)}

最终报告 (Final Report):
{state["final_report"]}

需要提供以下调整建议 (Required adjustments):
1. 广告系列预算 (Campaign budgets)
2. CPC 出价 (CPC bids)
3. 调整时间 (Timing of changes)
4. 预期影响 (Expected impacts)

注意 (Note):
- 所有建议必须同时提供中英文说明
- 确保建议具有可操作性
- 必须符合指定的 JSON 格式"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    # Try to get valid JSON response with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            # Clean up response to extract JSON
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            adjustment_plan = json.loads(content)
            
            # Validate response structure
            if not all(key in adjustment_plan for key in ["campaign_adjustments", "global_recommendations"]):
                raise ValueError("Response missing required top-level keys")
            
            # Validate campaign adjustments
            for adjustment in adjustment_plan["campaign_adjustments"]:
                required_keys = ["campaign_id", "campaign_name", "budget_adjustment", "cpc_adjustment", "timing"]
                if not all(key in adjustment for key in required_keys):
                    raise ValueError("Campaign adjustment missing required keys")
                
                # Validate nested structures
                for adj_type in ["budget_adjustment", "cpc_adjustment"]:
                    adj = adjustment[adj_type]
                    if not all(key in adj for key in ["action", "percentage", "reason_zh", "reason_en"]):
                        raise ValueError(f"{adj_type} missing required keys")
                
                if not all(key in adjustment["timing"] for key in ["recommended_date", "urgency"]):
                    raise ValueError("Timing missing required keys")
            
            state["adjustment_plan"] = adjustment_plan
            break
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed to get valid JSON after {max_retries} attempts. Error: {str(e)}")
            continue
    
    # Save adjustment plan
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    with open(os.path.join(data_dir, "adjustment_plan.json"), "w") as f:
        json.dump(state["adjustment_plan"], f, indent=2)
    
    return state

def main():
    """Set up and run the LangGraph workflow."""
    # Initialize workflow graph
    workflow = StateGraph(State)
    
    # Add nodes
    workflow.add_node("load_initial_analysis", load_initial_analysis)
    workflow.add_node("check_data_completeness", check_data_completeness)
    workflow.add_node("detect_anomalies", detect_anomalies)
    workflow.add_node("generate_draft_report", generate_draft_report)
    workflow.add_node("generate_final_report", generate_final_report)
    workflow.add_node("suggest_adjustments", suggest_adjustments)
    
    # Define edges
    workflow.add_edge("load_initial_analysis", "check_data_completeness")
    workflow.add_edge("check_data_completeness", "detect_anomalies")
    workflow.add_edge("detect_anomalies", "generate_draft_report")
    workflow.add_edge("generate_draft_report", "generate_final_report")
    workflow.add_edge("generate_final_report", "suggest_adjustments")
    workflow.add_edge("suggest_adjustments", END)
    
    # Set entry point
    workflow.set_entry_point("load_initial_analysis")
    
    # Compile workflow
    app = workflow.compile()
    
    # Run workflow with empty initial state
    initial_state: State = {
        "initial_analysis": {},
        "cleaned_analysis": {},
        "anomaly_report": {},
        "draft_report": "",
        "final_report": "",
        "adjustment_plan": {}
    }
    
    app.invoke(initial_state)

if __name__ == "__main__":
    main()
