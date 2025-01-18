"""
History Analyzer for Campaign Data

This module processes campaign history data to analyze patterns, changes, and scheduled operations.
It works with data retrieved from data_fetcher.py to provide insights about campaign performance
and behavior over time.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import json
import pytz
from dataclasses import dataclass

@dataclass
class CampaignChange:
    """Represents a single change in campaign history."""
    campaign_id: str
    change_time: datetime
    change_type: str
    previous_value: str
    new_value: str
    metadata: Dict[str, str]

@dataclass
class HourlyState:
    """Represents the state of a campaign for a specific hour."""
    campaign_id: str
    date: datetime
    hour: int
    campaign_status: str
    campaign_status_percentage: float
    budget_status: str
    budget_status_percentage: float
    budget_amount: float
    budget_amount_percentage: float

@dataclass
class DailySummary:
    """Represents daily summary statistics for a campaign."""
    campaign_id: str
    date: datetime
    campaign_status_changes: int
    budget_status_changes: int
    budget_amount_changes: int
    downtime_day_ratio: float
    downtime_periods: Dict[int, float]  # hour -> ratio

@dataclass
class ScheduledOperation:
    """Represents a detected scheduled operation pattern."""
    campaign_id: str
    operation_type: str  # 'START', 'STOP', 'BUDGET'
    scheduled_time: datetime
    value: Optional[str] = None  # For budget amounts

class HistoryAnalyzer:
    """
    Analyzes campaign history data to provide insights about changes, patterns,
    and scheduled operations.
    """
    
    def __init__(self):
        """Initialize the History Analyzer."""
        self.pacific_tz = pytz.timezone("US/Pacific")
    
    def parse_and_filter_history_data(self, campaign_history: List[Dict]) -> List[CampaignChange]:
        """
        Parse and filter raw campaign history data.
        
        Args:
            campaign_history: Raw campaign history data from data_fetcher
            
        Returns:
            List of CampaignChange objects with filtered and processed data
        """
        changes = []
        for record in campaign_history:
            try:
                metadata = json.loads(record.get('metadata', '{}'))
            except json.JSONDecodeError:
                metadata = {}
                
            change = CampaignChange(
                campaign_id=record['campaign_id'],
                change_time=self._convert_to_us_time(record['change_time']),
                change_type=record['change_type'],
                previous_value=record['previous_value'],
                new_value=record['new_value'],
                metadata=metadata
            )
            changes.append(change)
        return changes
    
    def reconstruct_campaign_hourly_data(self, 
                                       changes: List[CampaignChange],
                                       date: datetime) -> List[HourlyState]:
        """
        Reconstruct hourly campaign states for a specific date.
        
        Args:
            changes: List of campaign changes
            date: The date to analyze
            
        Returns:
            List of HourlyState objects representing campaign state for each hour
        """
        hourly_states = []
        
        # Filter changes for the given date
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        relevant_changes = [c for c in changes if day_start <= c.change_time <= day_end]
        
        if not relevant_changes:
            # If no changes, create default states for all hours
            campaign_id = changes[0].campaign_id if changes else "unknown"
            return [
                HourlyState(
                    campaign_id=campaign_id,
                    date=date,
                    hour=hour,
                    campaign_status="Paused",
                    campaign_status_percentage=1.0,
                    budget_status="In Budget",
                    budget_status_percentage=1.0,
                    budget_amount=0.0,
                    budget_amount_percentage=1.0
                )
                for hour in range(24)
            ]
        
        # Initialize state tracking
        current_status = relevant_changes[0].previous_value
        current_budget = "In Budget"
        current_budget_amount = 0.0
        
        # Process each hour
        for hour in range(24):
            hour_start = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            hour_end = date.replace(hour=hour, minute=59, second=59, microsecond=999999)
            
            # Get changes within this hour
            hour_changes = [c for c in relevant_changes if hour_start <= c.change_time <= hour_end]
            
            # Calculate time-weighted values
            status_time = {"Paused": 0, "Deliver": 0}
            budget_time = {"In Budget": 0, "Out of Budget": 0}
            total_minutes = 60
            
            if hour_changes:
                prev_time = hour_start
                for change in hour_changes:
                    minutes = int((change.change_time - prev_time).total_seconds() // 60)
                    
                    if change.change_type == "STATUS":
                        status_time[current_status] += minutes
                        current_status = change.new_value
                    elif change.change_type == "IN_BUDGET":
                        budget_status = "In Budget" if change.new_value == "1" else "Out of Budget"
                        budget_time[current_budget] += minutes
                        current_budget = budget_status
                        
                    prev_time = change.change_time
                
                # Add remaining time
                remaining_minutes = int((hour_end - prev_time).total_seconds() // 60)
                status_time[current_status] += remaining_minutes
                budget_time[current_budget] += remaining_minutes
            else:
                # No changes in this hour
                status_time[current_status] = total_minutes
                budget_time[current_budget] = total_minutes
            
            # Create hourly state
            state = HourlyState(
                campaign_id=relevant_changes[0].campaign_id,
                date=date,
                hour=hour,
                campaign_status=max(status_time.items(), key=lambda x: x[1])[0],
                campaign_status_percentage=max(status_time.values()) / total_minutes,
                budget_status=max(budget_time.items(), key=lambda x: x[1])[0],
                budget_status_percentage=max(budget_time.values()) / total_minutes,
                budget_amount=current_budget_amount,
                budget_amount_percentage=1.0  # Simplified for now
            )
            hourly_states.append(state)
        
        return hourly_states
    
    def summarize_campaign_changes(self,
                                 hourly_states: List[HourlyState]) -> DailySummary:
        """
        Generate daily summary of campaign changes and downtime.
        
        Args:
            hourly_states: List of hourly campaign states
            
        Returns:
            DailySummary object with campaign statistics
        """
        if not hourly_states:
            raise ValueError("No hourly states provided for summarization")
            
        # Initialize counters
        campaign_status_changes = 0
        budget_status_changes = 0
        budget_amount_changes = 0
        downtime_periods = {}
        
        # Track previous states
        prev_campaign_status = hourly_states[0].campaign_status
        prev_budget_status = hourly_states[0].budget_status
        prev_budget_amount = hourly_states[0].budget_amount
        
        # Analyze each hour's state
        for state in hourly_states:
            # Count status changes
            if state.campaign_status != prev_campaign_status:
                campaign_status_changes += 1
            if state.budget_status != prev_budget_status:
                budget_status_changes += 1
            if state.budget_amount != prev_budget_amount:
                budget_amount_changes += 1
                
            # Track downtime (Deliver but Out of Budget)
            if state.campaign_status == "Deliver" and state.budget_status == "Out of Budget":
                downtime_periods[state.hour] = state.budget_status_percentage
                
            # Update previous states
            prev_campaign_status = state.campaign_status
            prev_budget_status = state.budget_status
            prev_budget_amount = state.budget_amount
        
        # Calculate downtime ratio
        total_downtime = sum(downtime_periods.values())
        downtime_day_ratio = total_downtime / 24.0  # Normalize to daily ratio
        
        return DailySummary(
            campaign_id=hourly_states[0].campaign_id,
            date=hourly_states[0].date,
            campaign_status_changes=campaign_status_changes,
            budget_status_changes=budget_status_changes,
            budget_amount_changes=budget_amount_changes,
            downtime_day_ratio=downtime_day_ratio,
            downtime_periods=downtime_periods
        )
    
    def detect_scheduled_operations(self,
                                  changes: List[CampaignChange]) -> List[ScheduledOperation]:
        """
        Detect patterns in campaign operations that suggest scheduling.
        
        Args:
            changes: List of campaign changes to analyze
            
        Returns:
            List of detected ScheduledOperation patterns
        """
        if not changes:
            return []
            
        # Sort changes by time
        sorted_changes = sorted(changes, key=lambda x: x.change_time)
        
        # Group changes by hour and type
        hour_patterns = {}  # (hour, change_type, new_value) -> count
        for change in sorted_changes:
            hour = change.change_time.hour
            key = (hour, change.change_type, change.new_value)
            hour_patterns[key] = hour_patterns.get(key, 0) + 1
        
        # Detect patterns (threshold: occurs on at least 2 different days)
        operations = []
        for (hour, change_type, new_value), count in hour_patterns.items():
            if count >= 2:  # Pattern occurs at least twice
                if change_type == "STATUS":
                    op_type = "START" if new_value == "Deliver" else "STOP"
                    # Use the first occurrence's date with the pattern's hour
                    base_time = sorted_changes[0].change_time.replace(hour=hour)
                    operations.append(
                        ScheduledOperation(
                            campaign_id=sorted_changes[0].campaign_id,
                            operation_type=op_type,
                            scheduled_time=base_time,
                            value=new_value
                        )
                    )
                elif change_type == "IN_BUDGET":
                    base_time = sorted_changes[0].change_time.replace(hour=hour)
                    operations.append(
                        ScheduledOperation(
                            campaign_id=sorted_changes[0].campaign_id,
                            operation_type="BUDGET",
                            scheduled_time=base_time,
                            value="In Budget" if new_value == "1" else "Out of Budget"
                        )
                    )
        
        return operations
    
    def _convert_to_us_time(self, epoch_ms: int) -> datetime:
        """
        Convert epoch milliseconds to US Pacific time.
        
        Args:
            epoch_ms: Timestamp in milliseconds since epoch
            
        Returns:
            datetime object in US/Pacific timezone
        """
        epoch_seconds = epoch_ms / 1000
        naive_dt = datetime.fromtimestamp(epoch_seconds, self.pacific_tz)
        return naive_dt
