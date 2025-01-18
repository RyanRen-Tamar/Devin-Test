import unittest
from datetime import datetime
import pytz
from history_analyzer import (
    HistoryAnalyzer,
    CampaignChange,
    HourlyState,
    DailySummary,
    ScheduledOperation
)

class TestHistoryAnalyzer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = HistoryAnalyzer()
        self.pacific_tz = pytz.timezone("US/Pacific")
        
        # Sample campaign changes for testing
        self.sample_changes = [
            CampaignChange(
                campaign_id="camp1",
                change_time=self._create_pacific_time(2024, 1, 1, 8, 0),
                change_type="STATUS",
                previous_value="Paused",
                new_value="Deliver",
                metadata={"Budget type": "daily"}
            ),
            CampaignChange(
                campaign_id="camp1",
                change_time=self._create_pacific_time(2024, 1, 1, 12, 0),
                change_type="IN_BUDGET",
                previous_value="1",
                new_value="0",
                metadata={"Budget type": "daily"}
            ),
            CampaignChange(
                campaign_id="camp1",
                change_time=self._create_pacific_time(2024, 1, 1, 16, 0),
                change_type="STATUS",
                previous_value="Deliver",
                new_value="Paused",
                metadata={"Budget type": "daily"}
            )
        ]
    
    def _create_pacific_time(self, year, month, day, hour, minute):
        """Helper to create Pacific timezone datetime objects."""
        naive_dt = datetime(year, month, day, hour, minute)
        return self.pacific_tz.localize(naive_dt)
    
    def test_timezone_conversion(self):
        """Test conversion from epoch ms to US Pacific time."""
        # Test regular time (PST)
        winter_epoch_ms = 1704124800000  # 2024-01-01 08:00:00 PST
        winter_time = self.analyzer._convert_to_us_time(winter_epoch_ms)
        self.assertEqual(winter_time.hour, 8)
        self.assertEqual(winter_time.tzname(), "PST")
        
        # Test daylight savings time (PDT)
        summer_epoch_ms = 1688223600000  # 2023-07-01 08:00:00 PDT
        summer_time = self.analyzer._convert_to_us_time(summer_epoch_ms)
        self.assertEqual(summer_time.hour, 8)
        self.assertEqual(summer_time.tzname(), "PDT")
    
    def test_parse_and_filter_history_data(self):
        """Test parsing and filtering of campaign history data."""
        raw_data = [
            {
                "campaign_id": "camp1",
                "change_time": 1704124800000,  # 2024-01-01 08:00:00 PST
                "change_type": "STATUS",
                "previous_value": "Paused",
                "new_value": "Deliver",
                "metadata": '{"Budget type": "daily"}'
            }
        ]
        
        changes = self.analyzer.parse_and_filter_history_data(raw_data)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].campaign_id, "camp1")
        self.assertEqual(changes[0].change_type, "STATUS")
        self.assertEqual(changes[0].new_value, "Deliver")
    
    def test_reconstruct_campaign_hourly_data(self):
        """Test reconstruction of hourly campaign states."""
        date = self._create_pacific_time(2024, 1, 1, 0, 0)
        hourly_states = self.analyzer.reconstruct_campaign_hourly_data(
            self.sample_changes, date
        )
        
        # Should have 24 hours of data
        self.assertEqual(len(hourly_states), 24)
        
        # Check state at 8:00 (campaign started)
        hour_8_state = next(s for s in hourly_states if s.hour == 8)
        self.assertEqual(hour_8_state.campaign_status, "Deliver")
        
        # Check state at 12:00 (went out of budget)
        hour_12_state = next(s for s in hourly_states if s.hour == 12)
        self.assertEqual(hour_12_state.budget_status, "Out of Budget")
        
        # Check state at 16:00 (campaign paused)
        hour_16_state = next(s for s in hourly_states if s.hour == 16)
        self.assertEqual(hour_16_state.campaign_status, "Paused")
    
    def test_summarize_campaign_changes(self):
        """Test summarization of campaign changes and downtime calculation."""
        date = self._create_pacific_time(2024, 1, 1, 0, 0)
        hourly_states = self.analyzer.reconstruct_campaign_hourly_data(
            self.sample_changes, date
        )
        summary = self.analyzer.summarize_campaign_changes(hourly_states)
        
        # Should detect 2 status changes (Paused->Deliver, Deliver->Paused)
        self.assertEqual(summary.campaign_status_changes, 2)
        
        # Should detect 1 budget status change (In->Out)
        self.assertEqual(summary.budget_status_changes, 1)
        
        # Should have downtime between 12:00-16:00 (4 hours)
        self.assertGreater(summary.downtime_day_ratio, 0)
        self.assertEqual(len(summary.downtime_periods), 4)  # 4 hours of downtime
    
    def test_detect_scheduled_operations(self):
        """Test detection of scheduled operation patterns."""
        # Create repeated pattern over multiple days
        repeated_changes = []
        for day in range(1, 4):  # 3 days
            repeated_changes.extend([
                CampaignChange(
                    campaign_id="camp1",
                    change_time=self._create_pacific_time(2024, 1, day, 8, 0),
                    change_type="STATUS",
                    previous_value="Paused",
                    new_value="Deliver",
                    metadata={"Budget type": "daily"}
                ),
                CampaignChange(
                    campaign_id="camp1",
                    change_time=self._create_pacific_time(2024, 1, day, 20, 0),
                    change_type="STATUS",
                    previous_value="Deliver",
                    new_value="Paused",
                    metadata={"Budget type": "daily"}
                )
            ])
        
        operations = self.analyzer.detect_scheduled_operations(repeated_changes)
        
        # Should detect START operations at 8:00
        start_ops = [op for op in operations if op.operation_type == "START"]
        self.assertTrue(all(op.scheduled_time.hour == 8 for op in start_ops))
        
        # Should detect STOP operations at 20:00
        stop_ops = [op for op in operations if op.operation_type == "STOP"]
        self.assertTrue(all(op.scheduled_time.hour == 20 for op in stop_ops))

if __name__ == '__main__':
    unittest.main()
