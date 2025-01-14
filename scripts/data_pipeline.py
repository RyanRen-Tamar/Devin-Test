"""Data pipeline for LAMTA's Ad Performance Monitoring using LangGraph architecture."""

import json
import os
from datetime import datetime
from typing import TypedDict, Annotated, List, Dict
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

# Type definitions for state management
class CampaignMetrics(TypedDict):
    campaign_id: str
    campaign_name: str
    date: str
    daily_spend_ratio: float
    weekly_spend_ratio: float
    spend: float
    impressions: int
    clicks: int
    ad_sales: float
    units_sold: int
    cpc: float
    roi: float
    roi_status: str
    acos: float
    tacos: float
    inventory_days_left: int
    inventory_status: str
    historical_values: Dict
    missing_data_flag: bool
    notes: str

class ProductListing(TypedDict):
    asin: str
    sku: str
    product_name: str
    current_price: float
    stock_quantity: int
    coupon_active: bool
    deal_active: bool
    prime_exclusive: bool
    estimated_daily_sales: int

class BudgetConfig(TypedDict):
    budget_id: str
    campaign_id: str
    budget_type: str
    budget_amount: float
    threshold_percentage_high: float
    threshold_percentage_low: float
    promotion_start_date: str | None
    promotion_end_date: str | None
    promotion_target_uplift: float | None

class State(TypedDict):
    campaign_metrics: List[CampaignMetrics]
    product_listings: List[ProductListing]
    budget_configs: List[BudgetConfig]
    analysis_results: Dict

def load_data(state: State) -> State:
    """Load data from JSON files and merge into state."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    
    # Load campaign metrics
    with open(os.path.join(data_dir, "ad_metrics.json"), "r") as f:
        campaign_data = json.load(f)
    
    # Load product listings
    with open(os.path.join(data_dir, "product_listings.json"), "r") as f:
        listing_data = json.load(f)
    
    # Load budget configurations
    with open(os.path.join(data_dir, "budget_settings.json"), "r") as f:
        budget_data = json.load(f)
    
    return {
        "campaign_metrics": campaign_data["campaign_metrics"],
        "product_listings": listing_data["listings"],
        "budget_configs": budget_data["budget_configs"],
        "analysis_results": {}
    }

def analyze_metrics(state: State) -> State:
    """Analyze metrics and compute derived values."""
    analysis_results = {
        "campaigns": [],
        "global_stats": {
            "total_spend": 0,
            "total_sales": 0,
            "average_roi": 0,
            "average_acos": 0
        }
    }
    
    # Process each campaign
    for campaign in state["campaign_metrics"]:
        # Find corresponding budget config
        budget_config = next(
            (b for b in state["budget_configs"] if b["campaign_id"] == campaign["campaign_id"]),
            None
        )
        
        # Calculate budget utilization
        if budget_config:
            budget_utilization = (campaign["spend"] / budget_config["budget_amount"]) * 100
            budget_status = (
                "OverBudget" if budget_utilization > budget_config["threshold_percentage_high"]
                else "UnderBudget" if budget_utilization < budget_config["threshold_percentage_low"]
                else "Normal"
            )
        else:
            budget_utilization = None
            budget_status = "NoBudgetConfig"
        
        # Update global stats
        analysis_results["global_stats"]["total_spend"] += campaign["spend"]
        analysis_results["global_stats"]["total_sales"] += campaign["ad_sales"]
        
        # Prepare campaign analysis
        campaign_analysis = {
            "campaign_id": campaign["campaign_id"],
            "campaign_name": campaign["campaign_name"],
            "metrics": {
                "spend": campaign["spend"],
                "sales": campaign["ad_sales"],
                "roi": campaign["roi"],
                "acos": campaign["acos"],
                "daily_spend_ratio": campaign["daily_spend_ratio"]
            },
            "status": {
                "budget": budget_status,
                "roi": campaign["roi_status"],
                "inventory": campaign["inventory_status"]
            },
            "historical_comparison": {
                "roi_vs_avg": campaign["roi"] - campaign["historical_values"]["roi_avg"],
                "acos_vs_avg": campaign["acos"] - campaign["historical_values"]["acos_avg"],
                "spend_ratio_vs_avg": campaign["daily_spend_ratio"] - campaign["historical_values"]["daily_spend_ratio_avg"]
            }
        }
        
        analysis_results["campaigns"].append(campaign_analysis)
    
    # Calculate global averages
    num_campaigns = len(state["campaign_metrics"])
    if num_campaigns > 0:
        analysis_results["global_stats"]["average_roi"] = sum(c["roi"] for c in state["campaign_metrics"]) / num_campaigns
        analysis_results["global_stats"]["average_acos"] = sum(c["acos"] for c in state["campaign_metrics"]) / num_campaigns
    
    state["analysis_results"] = analysis_results
    return state

def save_results(state: State) -> State:
    """Save analysis results to initial_analysis.json."""
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    output_file = os.path.join(output_dir, "initial_analysis.json")
    
    with open(output_file, "w") as f:
        json.dump(state["analysis_results"], f, indent=2)
    
    return state

def main():
    """Set up and run the LangGraph workflow."""
    # Initialize workflow graph
    workflow = StateGraph(State)
    
    # Add nodes
    workflow.add_node("load_data", load_data)
    workflow.add_node("analyze_metrics", analyze_metrics)
    workflow.add_node("save_results", save_results)
    
    # Define edges
    workflow.add_edge("load_data", "analyze_metrics")
    workflow.add_edge("analyze_metrics", "save_results")
    workflow.add_edge("save_results", END)
    
    # Set entry point
    workflow.set_entry_point("load_data")
    
    # Compile workflow
    app = workflow.compile()
    
    # Run workflow with empty initial state
    initial_state: State = {
        "campaign_metrics": [],
        "product_listings": [],
        "budget_configs": [],
        "analysis_results": {}
    }
    
    app.invoke(initial_state)

if __name__ == "__main__":
    main()
