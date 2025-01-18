"""
History Analyzer for Campaign Data

This module processes campaign history data to analyze patterns, changes, and scheduled operations.
It works with data retrieved from data_fetcher.py to provide insights about campaign performance
and behavior over time.
"""

from datetime import datetime, timedelta, timezone
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
        filtered_changes = []
        
        for record in campaign_history:
            # Convert timestamp to US Western time
            change_time = self._convert_to_us_time(record['change_time'])
            
            # Extract metadata fields if they exist
            metadata = {}
            if 'metadata' in record and record['metadata']:
                try:
                    if isinstance(record['metadata'], str):
                        metadata_dict = json.loads(record['metadata'])
                    else:
                        metadata_dict = record['metadata']
                    
                    metadata = {
                        'Budget type': metadata_dict.get('Budget type', ''),
                        'placement': metadata_dict.get('placement', '')
                    }
                except (json.JSONDecodeError, AttributeError):
                    # If metadata is invalid JSON or doesn't have expected fields
                    metadata = {'Budget type': '', 'placement': ''}
            
            # Create CampaignChange object
            change = CampaignChange(
                campaign_id=str(record['campaign_id']),
                change_time=change_time,
                change_type=record['change_type'],
                previous_value=str(record['previous_value']),
                new_value=str(record['new_value']),
                metadata=metadata
            )
            
            # Only include relevant change types
            if change.change_type in ['STATUS', 'IN_BUDGET']:
                filtered_changes.append(change)
        
        # Sort changes by time
        filtered_changes.sort(key=lambda x: x.change_time)
        
        return filtered_changes
    
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
        # Filter changes for the specific date
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        day_changes = [
            change for change in changes
            if date_start <= change.change_time <= date_end
        ]
        
        if not day_changes:
            return []
        
        # Group changes by campaign
        campaign_changes: Dict[str, List[CampaignChange]] = {}
        for change in day_changes:
            if change.campaign_id not in campaign_changes:
                campaign_changes[change.campaign_id] = []
            campaign_changes[change.campaign_id].append(change)
        
        hourly_states = []
        
        # Process each campaign
        for campaign_id, campaign_day_changes in campaign_changes.items():
            # Initialize default states
            current_campaign_status = campaign_day_changes[0].previous_value
            current_budget_status = "In Budget"  # Default state
            current_budget_amount = 0.0
            
            # Process each hour
            for hour in range(24):
                hour_start = date_start + timedelta(hours=hour)
                hour_end = hour_start + timedelta(hours=1)
                
                # Find changes that occurred during this hour
                hour_changes = [
                    change for change in campaign_day_changes
                    if hour_start <= change.change_time < hour_end
                ]
                
                # Calculate state percentages based on time spent in each state
                campaign_status_times: Dict[str, float] = {current_campaign_status: 0.0}
                budget_status_times: Dict[str, float] = {current_budget_status: 0.0}
                budget_amount_times: Dict[float, float] = {current_budget_amount: 0.0}
                
                last_change_time = hour_start
                
                # Process each change in the hour
                for change in hour_changes:
                    time_in_state = (change.change_time - last_change_time).total_seconds() / 3600
                    
                    if change.change_type == "STATUS":
                        campaign_status_times[current_campaign_status] = campaign_status_times.get(
                            current_campaign_status, 0.0) + time_in_state
                        current_campaign_status = change.new_value
                    elif change.change_type == "IN_BUDGET":
                        budget_status_times[current_budget_status] = budget_status_times.get(
                            current_budget_status, 0.0) + time_in_state
                        current_budget_status = "In Budget" if change.new_value == "1" else "Out of Budget"
                    
                    last_change_time = change.change_time
                
                # Add remaining time in the hour
                time_remaining = (hour_end - last_change_time).total_seconds() / 3600
                campaign_status_times[current_campaign_status] = campaign_status_times.get(
                    current_campaign_status, 0.0) + time_remaining
                budget_status_times[current_budget_status] = budget_status_times.get(
                    current_budget_status, 0.0) + time_remaining
                budget_amount_times[current_budget_amount] = budget_amount_times.get(
                    current_budget_amount, 0.0) + time_remaining
                
                # Find dominant states (highest percentage)
                dominant_campaign_status = max(campaign_status_times.items(), key=lambda x: x[1])
                dominant_budget_status = max(budget_status_times.items(), key=lambda x: x[1])
                dominant_budget_amount = max(budget_amount_times.items(), key=lambda x: x[1])
                
                # Create hourly state
                state = HourlyState(
                    campaign_id=campaign_id,
                    date=date,
                    hour=hour,
                    campaign_status=dominant_campaign_status[0],
                    campaign_status_percentage=dominant_campaign_status[1],
                    budget_status=dominant_budget_status[0],
                    budget_status_percentage=dominant_budget_status[1],
                    budget_amount=dominant_budget_amount[0],
                    budget_amount_percentage=dominant_budget_amount[1]
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
            return DailySummary(
                campaign_id="",
                date=datetime.now(),
                campaign_status_changes=0,
                budget_status_changes=0,
                budget_amount_changes=0,
                downtime_day_ratio=0.0,
                downtime_periods={}
            )
        
        # All states should be for the same campaign and date
        campaign_id = hourly_states[0].campaign_id
        date = hourly_states[0].date
        
        # Sort states by hour to ensure proper order
        states = sorted(hourly_states, key=lambda x: x.hour)
        
        # Count changes by comparing adjacent hours
        campaign_status_changes = 0
        budget_status_changes = 0
        budget_amount_changes = 0
        downtime_periods: Dict[int, float] = {}
        
        prev_state = None
        for state in states:
            if prev_state:
                # Count status changes
                if state.campaign_status != prev_state.campaign_status:
                    campaign_status_changes += 1
                
                # Count budget status changes
                if state.budget_status != prev_state.budget_status:
                    budget_status_changes += 1
                
                # Count budget amount changes
                if abs(state.budget_amount - prev_state.budget_amount) > 0.01:  # Use small epsilon for float comparison
                    budget_amount_changes += 1
            
            # Track downtime (Deliver status but Out of Budget)
            if (state.campaign_status == "Deliver" and 
                state.budget_status == "Out of Budget"):
                downtime_periods[state.hour] = max(
                    state.campaign_status_percentage,
                    state.budget_status_percentage
                ) / 100.0  # Convert to ratio
            
            prev_state = state
        
        # Calculate overall downtime ratio for the day
        total_downtime = sum(downtime_periods.values())
        downtime_day_ratio = total_downtime / 24.0  # Normalize by 24 hours
        
        return DailySummary(
            campaign_id=campaign_id,
            date=date,
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
        
        # Group changes by campaign
        campaign_changes: Dict[str, List[CampaignChange]] = {}
        for change in changes:
            if change.campaign_id not in campaign_changes:
                campaign_changes[change.campaign_id] = []
            campaign_changes[change.campaign_id].append(change)
        
        scheduled_operations = []
        
        for campaign_id, campaign_changes_list in campaign_changes.items():
            # Sort changes by time
            sorted_changes = sorted(campaign_changes_list, key=lambda x: x.change_time)
            
            # Group changes by type and hour of day
            status_changes_by_hour: Dict[int, List[CampaignChange]] = {}
            budget_changes_by_hour: Dict[int, List[CampaignChange]] = {}
            
            for change in sorted_changes:
                hour = change.change_time.hour
                
                if change.change_type == "STATUS":
                    if hour not in status_changes_by_hour:
                        status_changes_by_hour[hour] = []
                    status_changes_by_hour[hour].append(change)
                elif change.change_type == "IN_BUDGET":
                    if hour not in budget_changes_by_hour:
                        budget_changes_by_hour[hour] = []
                    budget_changes_by_hour[hour].append(change)
            
            # Detect status change patterns (start/stop)
            for hour, hour_changes in status_changes_by_hour.items():
                if len(hour_changes) >= 2:  # Need at least 2 changes to establish pattern
                    # Check if changes consistently occur at this hour
                    dates = [change.change_time.date() for change in hour_changes]
                    unique_dates = len(set(dates))
                    if unique_dates >= 2:  # Pattern occurs on multiple days
                        # Look for start/stop patterns
                        for change in hour_changes:
                            if change.new_value == "Deliver":
                                scheduled_operations.append(
                                    ScheduledOperation(
                                        campaign_id=campaign_id,
                                        operation_type="START",
                                        scheduled_time=change.change_time,
                                        value=None
                                    )
                                )
                            elif change.new_value == "Paused":
                                scheduled_operations.append(
                                    ScheduledOperation(
                                        campaign_id=campaign_id,
                                        operation_type="STOP",
                                        scheduled_time=change.change_time,
                                        value=None
                                    )
                                )
            
            # Detect budget change patterns
            for hour, hour_changes in budget_changes_by_hour.items():
                if len(hour_changes) >= 2:  # Need at least 2 changes to establish pattern
                    # Check if changes consistently occur at this hour
                    dates = [change.change_time.date() for change in hour_changes]
                    unique_dates = len(set(dates))
                    if unique_dates >= 2:  # Pattern occurs on multiple days
                        for change in hour_changes:
                            if change.metadata.get('Budget type'):  # Only track budget changes with type
                                scheduled_operations.append(
                                    ScheduledOperation(
                                        campaign_id=campaign_id,
                                        operation_type="BUDGET",
                                        scheduled_time=change.change_time,
                                        value=change.new_value
                                    )
                                )
        
        return scheduled_operations
    
    def _convert_to_us_time(self, epoch_ms: int) -> datetime:
        """
        Convert epoch milliseconds to US Pacific time.
        Handles both standard time (PST) and daylight savings time (PDT).
        The input timestamp is expected to be in Pacific time.
        
        Args:
            epoch_ms: Timestamp in milliseconds since epoch (Pacific time)
            
        Returns:
            datetime object in US/Pacific timezone with proper DST handling
        """
        # Convert milliseconds to seconds and create naive datetime in Pacific time
        epoch_seconds = epoch_ms / 1000
        naive_dt = datetime.fromtimestamp(epoch_seconds, self.pacific_tz)
        return naive_dt
