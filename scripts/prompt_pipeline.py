"""Prompt pipeline for LAMTA's Ad Performance Monitoring using LangGraph architecture."""

import json
import os
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
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

from langchain.memory import ConversationBufferMemory
from typing import Optional

class MemoryEntry(TypedDict):
    """Type definition for memory entries."""
    phase: str
    timestamp: str
    findings: Dict[str, Any]
    confidence: float
    validation_status: bool
    decisions: List[str]

class ContextData(TypedDict):
    """Enhanced context with memory management."""
    current_phase: str
    memory_buffer: List[MemoryEntry]
    confidence_scores: Dict[str, float]
    validation_results: Dict[str, bool]
    historical_decisions: List[Dict[str, Any]]
    summary: Optional[str]  # Compressed context summary

class ValidationStatus(TypedDict):
    """Type definition for validation status tracking."""
    is_valid: bool
    errors: List[str]
    retry_count: int
    last_valid_state: Optional[str]

class State(TypedDict):
    """Enhanced state with ReAct context and validation tracking."""
    initial_analysis: Dict[str, Any]
    cleaned_analysis: Dict[str, Any]
    anomaly_report: Dict[str, Any]
    draft_report: str
    final_report: str
    adjustment_plan: Dict[str, Any]
    context: ContextData
    validation: ValidationStatus

def initialize_context() -> ContextData:
    """Initialize enhanced ReAct context with memory management."""
    return {
        "current_phase": "initialization",
        "memory_buffer": [],
        "confidence_scores": {},
        "validation_results": {},
        "historical_decisions": [],
        "summary": None
    }

def compress_memory(memory_buffer: List[MemoryEntry], max_entries: int = 10) -> Optional[str]:
    """Compress memory buffer into a summary when it grows too large."""
    if len(memory_buffer) <= max_entries:
        return None
    
    # Group findings by phase
    phase_findings = {}
    for entry in memory_buffer:
        phase = entry["phase"]
        if phase not in phase_findings:
            phase_findings[phase] = []
        phase_findings[phase].append(entry["findings"])
    
    # Create summary
    summary_parts = []
    for phase, findings_list in phase_findings.items():
        # Aggregate metrics and decisions
        metrics = {}
        decisions = set()
        for findings in findings_list:
            if "metrics" in findings:
                for metric, value in findings["metrics"].items():
                    if metric not in metrics:
                        metrics[metric] = []
                    metrics[metric].append(value)
            if "decisions" in findings:
                decisions.update(findings["decisions"])
        
        # Compute averages and ranges
        metrics_summary = {}
        for metric, values in metrics.items():
            metrics_summary[metric] = {
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values)
            }
        
        summary_parts.append({
            "phase": phase,
            "metrics_summary": metrics_summary,
            "key_decisions": list(decisions)
        })
    
    return json.dumps(summary_parts)

def update_context(state: State, phase: str, findings: Dict[str, Any]) -> None:
    """Update ReAct context with new findings and manage memory."""
    # Update current phase
    state["context"]["current_phase"] = phase
    
    # Create memory entry
    entry: MemoryEntry = {
        "phase": phase,
        "timestamp": datetime.now().isoformat(),
        "findings": findings,
        "confidence": state["context"]["confidence_scores"].get(phase, 0.0),
        "validation_status": state["context"]["validation_results"].get(phase, False),
        "decisions": [d["decision"] for d in state["context"]["historical_decisions"] if d["phase"] == phase]
    }
    
    # Add to memory buffer
    state["context"]["memory_buffer"].append(entry)
    
    # Compress memory if buffer is too large
    if len(state["context"]["memory_buffer"]) > 10:
        state["context"]["summary"] = compress_memory(state["context"]["memory_buffer"])
        # Keep only recent entries after compression
        state["context"]["memory_buffer"] = state["context"]["memory_buffer"][-5:]
    
    # Update historical decisions
    if "decision" in findings:
        state["context"]["historical_decisions"].append({
            "phase": phase,
            "timestamp": entry["timestamp"],
            "decision": findings["decision"]
        })

def validate_context(state: State, current_findings: Dict[str, Any]) -> float:
    """Validate current findings against historical context."""
    if not state["context"]["memory_buffer"]:
        return 1.0  # First analysis, assume high confidence
    
    # Compare with previous findings
    prev_entry = state["context"]["memory_buffer"][-1]
    prev_findings = prev_entry["findings"]
    
    # Calculate confidence score based on consistency
    confidence = 1.0
    
    # Adjust confidence based on metric stability
    if "metrics" in prev_findings and "metrics" in current_findings:
        for metric, value in current_findings["metrics"].items():
            if metric in prev_findings["metrics"]:
                prev_value = prev_findings["metrics"][metric]
                if isinstance(value, (int, float)) and isinstance(prev_value, (int, float)):
                    # Reduce confidence if large variations detected
                    variation = abs(value - prev_value) / max(abs(prev_value), 1)
                    if variation > 0.2:  # 20% threshold
                        confidence *= 0.8
    
    return confidence

def save_context(state: State) -> None:
    """Save ReAct context for analysis and debugging."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    context_file = os.path.join(data_dir, "react_context.json")
    
    with open(context_file, "w") as f:
        json.dump(state["context"], f, indent=2)

def load_initial_analysis(state: State) -> State:
    """Load initial analysis from JSON file and initialize context."""
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

def validate_chart_data(data: Dict[str, Any], chart_type: str) -> tuple[bool, List[str]]:
    """Validate chart data against business rules and data types.
    Returns:
        tuple: (is_valid: bool, errors: List[str])
    """
    errors = []
    try:
        # Common validation
        if not isinstance(data, dict) or "data" not in data or "type" not in data:
            errors.append("Invalid chart data structure")
            return False, errors
        
        if chart_type == "bar":
            # Budget utilization chart validation
            if not isinstance(data["data"], dict) or "datasets" not in data["data"] or "labels" not in data["data"]:
                errors.append("Invalid bar chart structure")
                return False, errors
            
            datasets = data["data"]["datasets"]
            if not isinstance(datasets, list) or len(datasets) != 1:
                errors.append("Bar chart must have exactly one dataset")
                return False, errors
            
            dataset = datasets[0]
            if not isinstance(dataset, dict) or "data" not in dataset or "label" not in dataset:
                errors.append("Invalid dataset structure in bar chart")
                return False, errors
            
            values = dataset["data"]
            if not all(isinstance(x, (int, float)) for x in values):
                errors.append("Non-numeric values in budget utilization data")
                return False, errors
                
            # Business rules for budget utilization
            if any(x < 0 for x in values):
                errors.append("Negative budget utilization detected")
                return False, errors
            if any(x > 200 for x in values):
                errors.append("Budget utilization exceeds 200%")
                return False, errors
            if any(x < 30 and dataset["label"] == "Budget Utilization %" for x in values):
                print(f"Warning: Low budget utilization detected: {min(values)}%")
            
        elif chart_type == "line":
            # ROI and ACOS trends validation
            if not isinstance(data["data"], dict) or "datasets" not in data["data"] or "labels" not in data["data"]:
                errors.append("Invalid line chart structure")
                return False, errors
            
            datasets = data["data"]["datasets"]
            if not isinstance(datasets, list) or len(datasets) != 2:
                errors.append("Line chart must have both ROI and ACOS datasets")
                return False, errors
            
            for dataset in datasets:
                if not isinstance(dataset, dict) or "data" not in dataset or "label" not in dataset:
                    errors.append("Invalid dataset structure in line chart")
                    return False, errors
                
                values = dataset["data"]
                if not all(isinstance(x, (int, float)) for x in values):
                    errors.append(f"Non-numeric values in {dataset['label']} data")
                    return False, errors
                
                # Business rules for ROI and ACOS
                if dataset["label"] == "ROI":
                    if any(x <= 0 for x in values):
                        errors.append("Error: ROI must be positive")
                        return False, errors
                    if any(x > 10 for x in values):
                        errors.append(f"Warning: Unusually high ROI detected: {max(values)}")
                elif dataset["label"] == "ACOS":
                    if any(x < 0 for x in values):
                        errors.append("Error: ACOS cannot be negative")
                        return False, errors
                    if any(x > 100 for x in values):
                        errors.append("Error: ACOS cannot exceed 100%")
                        return False, errors
                    if any(x < 5 for x in values):
                        errors.append(f"Warning: Unusually low ACOS detected: {min(values)}%")
            
        elif chart_type == "gauge":
            # Inventory days gauge validation
            if not isinstance(data["data"], dict):
                errors.append("Invalid gauge chart structure")
                return False, errors
            
            required_fields = ["value", "min", "max", "threshold"]
            if not all(field in data["data"] for field in required_fields):
                errors.append("Error: Missing required fields in gauge chart")
                return False, errors
            
            gauge_data = data["data"]
            if not all(isinstance(gauge_data[field], (int, float)) for field in required_fields):
                errors.append("Error: Non-numeric values in gauge data")
                return False, errors
            
            # Business rules for inventory
            if gauge_data["value"] < gauge_data["min"] or gauge_data["value"] > gauge_data["max"]:
                errors.append("Error: Inventory days out of valid range")
                return False, errors
            if gauge_data["value"] <= gauge_data["threshold"]:
                print(f"Warning: Low inventory detected: {gauge_data['value']} days left")
            if gauge_data["max"] != 30 or gauge_data["min"] != 0:
                errors.append("Error: Invalid inventory days range (must be 0-30)")
                return False, errors
            if gauge_data["threshold"] != 7:
                errors.append("Error: Invalid inventory warning threshold (must be 7)")
                return False, errors
        else:
            errors.append(f"Error: Unsupported chart type: {chart_type}")
            return False, errors
        
        return True, errors
    except (KeyError, TypeError, ValueError) as e:
        errors.append(f"Chart validation error: {str(e)}")
        return False, errors

def generate_final_report(state: State) -> State:
    """Prompt 4: Generate final report with charts and action plan."""
    system_prompt = """You are a senior business consultant and Amazon advertising strategist with 15+ years of e-commerce expertise.
Your task is to create an executive-level, bilingual report that drives business decisions through concrete data and strategic insights.

Key principles for your analysis:
1. Use natural business language:
   - Write like an experienced consultant, not an AI
   - Make definitive statements backed by data
   - Use industry-standard terminology
   - Avoid hedging words like "may," "might," or "could"

2. Demonstrate clear business value:
   - Quantify all impacts in revenue/profit terms
   - Compare metrics to industry benchmarks
   - Highlight competitive advantages
   - Show clear ROI for recommendations

3. Provide actionable insights:
   - Give specific, prioritized recommendations
   - Include implementation timelines
   - Define success metrics and KPIs
   - Estimate resource requirements

4. Connect insights strategically:
   - Show how budget affects ROI
   - Link inventory to revenue impact
   - Connect ACOS to market position
   - Demonstrate competitive implications

5. Focus on subscription value:
   - Highlight long-term optimization potential
   - Show trend analysis and forecasting
   - Include market intelligence
   - Demonstrate ongoing monitoring benefits

IMPORTANT: Your response must be in markdown format with the following structure:
# 亚马逊广告效果分析报告 (Amazon Advertising Performance Report)

## 执行摘要 (Executive Summary)
提供一个简明扼要的业务影响分析，包括：
- 当前业绩表现及其商业意义
- 关键机遇与风险的量化评估
- 预期的收入和利润影响
- 优先级最高的战略行动建议

(Provide a concise business impact analysis including:
- Current performance and business implications
- Quantified assessment of key opportunities and risks
- Expected revenue and profit impact
- Top priority strategic actions)

## 详细分析 (Detailed Analysis)

### 预算表现 (Budget Performance)
分析预算效率和策略性分配：
- 与行业标准的对标分析
- ROI 机会和风险评估
- 具体的优化建议及其商业价值
- 潜在的收入影响预测

(Budget efficiency and strategic allocation analysis:
- Benchmarking against industry standards
- ROI opportunities and risk assessment
- Specific optimization recommendations and business value
- Projected revenue impact)

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
盈利能力和市场竞争力分析：
- 与行业标准和竞争对手的对比
- 具体的利润优化机会
- 市场份额和竞争定位分析
- 建议实施后的收入预测

(Profitability and Market Competitiveness Analysis:
- Comparison with industry standards and competitors
- Specific profit optimization opportunities
- Market share and competitive positioning
- Revenue projections post-implementation)

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
库存和供应链战略分析：
- 供应链效率评估和优化建议
- 季节性需求趋势分析
- 库存优化对收入的影响
- 具体的库存管理策略

(Inventory and Supply Chain Strategic Analysis:
- Supply chain efficiency assessment and optimization
- Seasonal demand trend analysis
- Revenue impact of inventory optimization
- Specific inventory management strategies)

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
明确的优先级策略：
- 具体、可衡量的行动步骤
- 预期的业务成果和 ROI
- 实施时间表和里程碑
- 所需资源评估

(Clear prioritized strategy:
- Specific, measurable action steps
- Expected business outcomes and ROI
- Implementation timeline and milestones
- Resource requirements assessment)

## 后续步骤 (Next Steps)
战略性后续计划：
- 短期优先事项（0-30天）
- 中期计划（30-90天）
- 长期战略调整建议
- 成功指标和KPI定义

(Strategic next steps:
- Short-term priorities (0-30 days)
- Medium-term initiatives (30-90 days)
- Long-term strategy alignment recommendations
- Success metrics and KPI definitions)"""

    human_prompt = f"""请基于以下草稿报告和异常分析生成最终报告 (Please generate final report based on this draft and analysis):

草稿报告 (Draft Report):
{state["draft_report"]}

异常分析 (Anomaly Analysis):
{json.dumps(state["anomaly_report"], indent=2)}

要求 (Requirements):
1. 使用自然的商业语言 (Use natural business language):
   - 像经验丰富的顾问一样写作，避免AI式表达
   - 使用行业标准术语和专业词汇
   - 用果断的语气表达见解和建议

2. 突出具体商业价值 (Emphasize concrete business value):
   - 量化每项建议的收入/利润影响
   - 与行业标准和竞争对手对标
   - 展示投资回报率和市场竞争优势
   - 预测实施后的业务增长

3. 加强分析深度 (Enhance analysis depth):
   - 展示趋势分析和预测
   - 包含市场竞争情报
   - 评估不同场景的影响
   - 提供具体的优化策略

4. 确保逻辑连贯 (Ensure logical flow):
   - 建立预算、ROI和库存之间的关联
   - 展示各指标间的因果关系
   - 连接短期行动和长期战略
   - 突出关键决策点

5. 提供明确时间表 (Provide clear timeline):
   - 区分短期、中期和长期行动
   - 设定具体的里程碑
   - 定义成功指标
   - 估算所需资源

注意 (Note):
- 使用数据支持每个结论 (Back every conclusion with data)
- 保持分析的连贯性 (Maintain analysis coherence)
- 突出订阅服务价值 (Highlight subscription value)
- 确保双语表达专业准确 (Ensure professional bilingual expression)"""

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
            
            # Extract and prepare chart data from state
            budget_data = []
            roi_acos_data = {"roi": [], "acos": []}
            inventory_data = None
            
            # Process campaign data for charts
            for campaign in state["cleaned_analysis"]["campaigns"]:
                # Budget utilization
                metrics = campaign["metrics"]
                budget_data.append({
                    "label": campaign["campaign_name"],
                    "value": round(metrics["daily_spend_ratio"] * 100, 2)
                })
                
                # ROI and ACOS trends
                roi_acos_data["roi"].append(round(metrics["roi"], 2))
                roi_acos_data["acos"].append(round(metrics["acos"], 2))
                
                # Track lowest inventory for gauge
                if campaign["status"]["inventory"] == "Warning":
                    days_left = metrics.get("inventory_days_left", 30)
                    if inventory_data is None or days_left < inventory_data["value"]:
                        inventory_data = {
                            "value": days_left,
                            "min": 0,
                            "max": 30,
                            "threshold": 7
                        }
            
            # Create chart configurations
            chart_configs = []
            
            # Budget utilization bar chart
            chart_configs.append({
                "type": "bar",
                "data": {
                    "labels": [d["label"] for d in budget_data],
                    "datasets": [{
                        "label": "Budget Utilization %",
                        "data": [d["value"] for d in budget_data]
                    }]
                }
            })
            
            # ROI & ACOS line chart
            chart_configs.append({
                "type": "line",
                "data": {
                    "labels": [f"Campaign {i+1}" for i in range(len(roi_acos_data["roi"]))],
                    "datasets": [
                        {
                            "label": "ROI",
                            "data": roi_acos_data["roi"]
                        },
                        {
                            "label": "ACOS",
                            "data": roi_acos_data["acos"]
                        }
                    ]
                }
            })
            
            # Inventory gauge chart
            if inventory_data:
                chart_configs.append({
                    "type": "gauge",
                    "data": inventory_data
                })
            else:
                # Default gauge if no warning inventory
                chart_configs.append({
                    "type": "gauge",
                    "data": {
                        "value": 30,
                        "min": 0,
                        "max": 30,
                        "threshold": 7
                    }
                })
            
            # Validate all chart configurations
            for chart_data in chart_configs:
                chart_type = chart_data.get("type")
                if not validate_chart_data(chart_data, chart_type):
                    raise ValueError(f"Invalid data for chart type: {chart_type}")
            
            # Ensure all required chart types are present
            chart_types = [c["type"] for c in chart_configs]
            required_types = ["bar", "line", "gauge"]
            if not all(t in chart_types for t in required_types):
                raise ValueError("Missing required chart types")
            
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
    """Prompt 5: Suggest budget and CPC adjustments with ReAct context."""
    # Include context in system prompt for better consistency
    prev_context = ""
    if state["context"]["memory_buffer"]:
        last_entry = state["context"]["memory_buffer"][-1]
        prev_context = f"\nPrevious analysis phase: {last_entry['phase']}\nKey findings: {json.dumps(last_entry['findings'], indent=2)}"
        if state["context"]["summary"]:
            prev_context += f"\n\nHistorical Context Summary:\n{state['context']['summary']}"
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
            
            # Update ReAct context
            context_update = {
                "adjustments_made": len(adjustment_plan["campaign_adjustments"]),
                "adjustment_summary": {
                    "budget_changes": sum(1 for adj in adjustment_plan["campaign_adjustments"] 
                                       if adj["budget_adjustment"]["action"] != "maintain"),
                    "cpc_changes": sum(1 for adj in adjustment_plan["campaign_adjustments"] 
                                     if adj["cpc_adjustment"]["action"] != "maintain")
                },
                "global_strategy": adjustment_plan["global_recommendations"]
            }
            update_context(state, "budget_adjustment", context_update)
            
            # Validate adjustments against context
            confidence = validate_context(state, context_update)
            state["context"]["confidence_scores"]["budget_adjustment"] = confidence
            
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

def validate_data_completeness(state: State) -> bool:
    """Validate data completeness and quality."""
    if not state["cleaned_analysis"]:
        return False
    
    # Check for required fields and data quality
    try:
        campaigns = state["cleaned_analysis"].get("campaigns", [])
        if not campaigns:
            return False
        
        for campaign in campaigns:
            required_fields = ["campaign_id", "metrics", "status"]
            if not all(field in campaign for field in required_fields):
                return False
            
            # Check for critical metrics
            metrics = campaign["metrics"]
            required_metrics = ["spend", "sales", "roi", "acos"]
            if not all(metric in metrics for metric in required_metrics):
                return False
    except (KeyError, TypeError):
        return False
    
    return True

def validate_anomaly_detection(state: State) -> bool:
    """Validate anomaly detection results."""
    if not state["anomaly_report"]:
        return False
    
    try:
        # Check for required sections
        required_sections = ["detailed_findings", "analysis_summary"]
        if not all(section in state["anomaly_report"] for section in required_sections):
            return False
        
        # Validate findings structure
        findings = state["anomaly_report"]["detailed_findings"]
        if not isinstance(findings, list):
            return False
        
        # Check critical anomaly threshold
        total_anomalies = state["anomaly_report"]["analysis_summary"]["total_anomalies"]
        if total_anomalies > 10:  # Arbitrary threshold, adjust as needed
            state["validation"]["errors"].append("Critical anomaly threshold exceeded")
            return False
    except (KeyError, TypeError):
        return False
    
    return True

def validate_report_generation(state: State) -> bool:
    """Validate report generation results."""
    if not state["final_report"]:
        return False
    
    try:
        # Check for required sections
        required_sections = [
            "# 亚马逊广告效果分析报告",
            "## 执行摘要",
            "## 详细分析",
            "### 预算表现",
            "### ROI 和 ACOS 分析",
            "### 库存状况"
        ]
        
        if not all(section in state["final_report"] for section in required_sections):
            return False
        
        # Validate chart configurations
        chart_sections = state["final_report"].split("```chart")
        if len(chart_sections) < 4:  # Expecting at least 3 charts
            return False
        
        for section in chart_sections[1:]:
            try:
                chart_json = section.split("```")[0].strip()
                chart_data = json.loads(chart_json)
                if not validate_chart_data(chart_data, chart_data.get("type", "")):
                    return False
            except (json.JSONDecodeError, ValueError):
                return False
    except (KeyError, TypeError):
        return False
    
    return True

def handle_data_recovery(state: State) -> State:
    """Recovery node for handling data validation failures."""
    # Update validation status
    state["validation"]["retry_count"] += 1
    
    if state["validation"]["retry_count"] > 3:
        # After 3 retries, try to proceed with partial data
        if not state["cleaned_analysis"].get("campaigns"):
            # No valid campaigns at all, cannot proceed
            raise ValueError("Critical data validation failure: No valid campaign data after retries")
        
        # Filter out invalid campaigns
        valid_campaigns = []
        for campaign in state["cleaned_analysis"].get("campaigns", []):
            if all(field in campaign for field in ["campaign_id", "metrics", "status"]):
                metrics = campaign["metrics"]
                if all(metric in metrics for metric in ["spend", "sales", "roi", "acos"]):
                    valid_campaigns.append(campaign)
        
        # Update state with only valid campaigns
        state["cleaned_analysis"]["campaigns"] = valid_campaigns
        state["validation"]["errors"].append(f"Proceeding with {len(valid_campaigns)} valid campaigns after recovery")
        
        # Update context
        update_context(state, "data_recovery", {
            "original_campaign_count": len(state["cleaned_analysis"].get("campaigns", [])),
            "valid_campaign_count": len(valid_campaigns),
            "recovery_action": "filtered_invalid_campaigns"
        })
    else:
        # On early retries, try to fill missing values with historical averages
        for campaign in state["cleaned_analysis"].get("campaigns", []):
            metrics = campaign.get("metrics", {})
            historical = campaign.get("historical_values", {})
            
            for metric in ["roi", "acos"]:
                if metric not in metrics and f"{metric}_avg" in historical:
                    metrics[metric] = historical[f"{metric}_avg"]
                    state["validation"]["errors"].append(f"Recovered {metric} using historical average for campaign {campaign['campaign_id']}")
        
        # Update context
        update_context(state, "data_recovery", {
            "retry_count": state["validation"]["retry_count"],
            "recovery_action": "used_historical_averages"
        })
    
    return state

def handle_anomaly_recovery(state: State) -> State:
    """Recovery node for handling anomaly detection failures."""
    # Update validation status
    state["validation"]["retry_count"] += 1
    
    if state["validation"]["retry_count"] > 3:
        # After 3 retries, adjust anomaly thresholds
        findings = state["anomaly_report"].get("detailed_findings", [])
        adjusted_findings = []
        
        for finding in findings:
            # Only keep high severity anomalies
            if finding.get("severity") == "high":
                adjusted_findings.append(finding)
        
        # Update anomaly report
        state["anomaly_report"]["detailed_findings"] = adjusted_findings
        state["anomaly_report"]["analysis_summary"]["total_anomalies"] = len(adjusted_findings)
        state["validation"]["errors"].append(f"Adjusted to {len(adjusted_findings)} critical anomalies after recovery")
        
        # Update context
        update_context(state, "anomaly_recovery", {
            "original_anomaly_count": len(findings),
            "critical_anomaly_count": len(adjusted_findings),
            "recovery_action": "filtered_low_severity_anomalies"
        })
    else:
        # On early retries, try to validate each finding individually
        findings = state["anomaly_report"].get("detailed_findings", [])
        valid_findings = []
        
        for finding in findings:
            try:
                # Validate metrics against thresholds
                metrics = finding.get("metrics", {})
                current = metrics.get("current_value", 0)
                threshold = metrics.get("threshold", 0)
                deviation = metrics.get("deviation_percentage", 0)
                
                if all(isinstance(x, (int, float)) for x in [current, threshold, deviation]):
                    valid_findings.append(finding)
            except (TypeError, ValueError):
                continue
        
        # Update anomaly report
        state["anomaly_report"]["detailed_findings"] = valid_findings
        state["anomaly_report"]["analysis_summary"]["total_anomalies"] = len(valid_findings)
        
        # Update context
        update_context(state, "anomaly_recovery", {
            "retry_count": state["validation"]["retry_count"],
            "recovery_action": "validated_individual_findings"
        })
    
    return state

def main():
    """Set up and run the LangGraph workflow with validation and recovery nodes."""
    print("[DEBUG] Starting prompt pipeline...")
    try:
        # Initialize workflow graph
        print("[DEBUG] Initializing workflow graph...")
        workflow = StateGraph(State)
        
        # Add nodes including context management and recovery
        print("[DEBUG] Adding nodes for data processing and recovery...")
        workflow.add_node("load_initial_analysis", load_initial_analysis)
        workflow.add_node("check_data_completeness", check_data_completeness)
        workflow.add_node("handle_data_recovery", handle_data_recovery)
        workflow.add_node("detect_anomalies", detect_anomalies)
        workflow.add_node("handle_anomaly_recovery", handle_anomaly_recovery)
        workflow.add_node("generate_draft_report", generate_draft_report)
        workflow.add_node("generate_final_report", generate_final_report)
        workflow.add_node("suggest_adjustments", suggest_adjustments)
        workflow.add_node("save_context", save_context)
    
    # Add validation conditions with recovery paths
        print("[DEBUG] Setting up validation conditions and recovery paths...")
        # Add conditional edges for data completeness validation
        def route_data_completeness(state: State) -> str:
            result = "detect_anomalies" if validate_data_completeness(state) else "handle_data_recovery"
            print(f"[DEBUG] Data completeness validation route: {result}")
            return result
        workflow.add_conditional_edges("check_data_completeness", route_data_completeness)
    
        # Add conditional edges for data recovery
        def route_data_recovery(state: State) -> str:
            result = "check_data_completeness" if state["validation"]["retry_count"] <= 3 else "detect_anomalies"
            print(f"[DEBUG] Data recovery route (retry {state['validation']['retry_count']}): {result}")
            return result
        workflow.add_conditional_edges("handle_data_recovery", route_data_recovery)
    
        # Add conditional edges for anomaly detection
        def route_anomaly_detection(state: State) -> str:
            result = "generate_draft_report" if validate_anomaly_detection(state) else "handle_anomaly_recovery"
            print(f"[DEBUG] Anomaly detection route: {result}")
            return result
        workflow.add_conditional_edges("detect_anomalies", route_anomaly_detection)
    
        # Add conditional edges for anomaly recovery
        def route_anomaly_recovery(state: State) -> str:
            result = "detect_anomalies" if state["validation"]["retry_count"] <= 3 else "generate_draft_report"
            print(f"[DEBUG] Anomaly recovery route (retry {state['validation']['retry_count']}): {result}")
            return result
        workflow.add_conditional_edges("handle_anomaly_recovery", route_anomaly_recovery)
    
        # Add conditional edges for report generation
        def route_report_generation(state: State) -> str:
            result = "suggest_adjustments" if validate_report_generation(state) else "generate_draft_report"
            print(f"[DEBUG] Report generation route: {result}")
            return result
        workflow.add_conditional_edges("generate_final_report", route_report_generation)
    
        # Add remaining edges
        print("[DEBUG] Adding remaining edges...")
        workflow.add_edge("load_initial_analysis", "check_data_completeness")
        workflow.add_edge("generate_draft_report", "generate_final_report")
        workflow.add_edge("suggest_adjustments", "save_context")
        workflow.add_edge("save_context", END)
        
        # Set entry point
        print("[DEBUG] Setting entry point...")
        workflow.set_entry_point("load_initial_analysis")
        
        # Compile workflow
        print("[DEBUG] Compiling workflow...")
        app = workflow.compile()
        
        # Run workflow with empty initial state including ReAct context and validation
        print("[DEBUG] Initializing state with ReAct context...")
        initial_state: State = {
            "initial_analysis": {},
            "cleaned_analysis": {},
            "anomaly_report": {},
            "draft_report": "",
            "final_report": "",
            "adjustment_plan": {},
            "context": initialize_context(),  # Initialize ReAct context
            "validation": {
                "is_valid": True,
                "errors": [],
                "retry_count": 0,
                "last_valid_state": None
            }
        }
        
        print("[DEBUG] Invoking workflow...")
        app.invoke(initial_state)
        print("[DEBUG] Workflow completed successfully.")
        
        # Save final context state
        print("[DEBUG] Saving final context...")
        save_context(initial_state)
        print("[DEBUG] Prompt pipeline completed successfully.")
    except Exception as e:
        print(f"[ERROR] Prompt pipeline failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()
