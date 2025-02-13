import pytest
from datetime import datetime, timedelta
from src.models import Resident, ResidentLevel, Pod, ShiftType, Shift, TimeOff
from src.scheduler import SchedulingConstraints

class TestSchedulingConstraints:
    @pytest.fixture
    def test_resident(self):
        """Create a test resident"""
        return Resident(
            id="TEST001",
            name="Test Resident",
            level=ResidentLevel.PGY2,
            pod_preferences=[Pod.PURPLE, Pod.ORANGE],
            time_off=[]
        )
    
    @pytest.fixture
    def base_date(self):
        """Return a base date for testing"""
        return datetime(2025, 2, 1)  # Using February 2025 as in the sample data
    
    def test_validate_consecutive_shifts_under_limit(self, test_resident, base_date):
        """Test that 6 or fewer consecutive shifts is valid"""
        # Create 6 consecutive day shifts
        shifts = [
            Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE,
                resident=test_resident
            )
            for i in range(6)
        ]
        
        assert SchedulingConstraints.validate_consecutive_shifts(shifts, test_resident) == True
    
    def test_validate_consecutive_shifts_over_limit(self, test_resident, base_date):
        """Test that more than 6 consecutive shifts is invalid"""
        # Create 7 consecutive day shifts
        shifts = [
            Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE,
                resident=test_resident
            )
            for i in range(7)
        ]
        
        assert SchedulingConstraints.validate_consecutive_shifts(shifts, test_resident) == False
    
    def test_validate_consecutive_shifts_with_gap(self, test_resident, base_date):
        """Test that shifts with a gap reset the consecutive count"""
        # Create shifts with a gap: 3 shifts, 1 day gap, 3 more shifts
        shifts = [
            Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE,
                resident=test_resident
            )
            for i in [0, 1, 2, 4, 5, 6]  # Note the gap at day 3
        ]
        
        assert SchedulingConstraints.validate_consecutive_shifts(shifts, test_resident) == True