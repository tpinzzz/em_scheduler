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

def test_validate_night_to_day_transition(self, test_resident, base_date):
    """Test transition from night shifts to day shifts requires 48h rest"""
    shifts = [
        # Block of night shifts
        Shift(
            date=base_date,
            shift_type=ShiftType.NIGHT,
            pod=Pod.PURPLE,
            resident=test_resident
        ),
        # Trying to start day shifts too soon (only 24h after last night)
        Shift(
            date=base_date + timedelta(days=2),  # This is too soon
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        )
    ]
    assert SchedulingConstraints.validate_shift_transitions(shifts, test_resident) == False

def test_validate_night_to_day_transition_valid(self, test_resident, base_date):
    """Test valid transition from night shifts to day shifts with 48h rest"""
    shifts = [
        # Block of night shifts
        Shift(
            date=base_date,
            shift_type=ShiftType.NIGHT,
            pod=Pod.PURPLE,
            resident=test_resident
        ),
        # Starting day shifts after proper rest (48h after last night shift ends)
        Shift(
            date=base_date + timedelta(days=3),  # This is good - full 48h after last night shift ends
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        )
    ]
    assert SchedulingConstraints.validate_shift_transitions(shifts, test_resident) == True

def test_validate_day_to_night_transition(self, test_resident, base_date):
    """Test transition from day shifts to night shifts requires 48h rest"""
    shifts = [
        # Block of day shifts
        Shift(
            date=base_date,
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        ),
        # Trying to start night shifts too soon
        Shift(
            date=base_date + timedelta(days=2),  # This is too soon
            shift_type=ShiftType.NIGHT,
            pod=Pod.PURPLE,
            resident=test_resident
        )
    ]
    assert SchedulingConstraints.validate_shift_transitions(shifts, test_resident) == False

def test_validate_day_to_night_transition_valid(self, test_resident, base_date):
    """Test valid transition from day shifts to night shifts with 48h rest"""
    shifts = [
        # Block of day shifts
        Shift(
            date=base_date,
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        ),
        # Starting night shifts after proper rest
        Shift(
            date=base_date + timedelta(days=3),  # This is good - full 48h rest
            shift_type=ShiftType.NIGHT,
            pod=Pod.PURPLE,
            resident=test_resident
        )
    ]
    assert SchedulingConstraints.validate_shift_transitions(shifts, test_resident) == True

def test_consecutive_shifts_same_type_valid(self, test_resident, base_date):
    """Test that consecutive shifts of the same type are allowed"""
    # Test consecutive night shifts
    night_shifts = [
        Shift(
            date=base_date + timedelta(days=i),
            shift_type=ShiftType.NIGHT,
            pod=Pod.PURPLE,
            resident=test_resident
        ) for i in range(3)
    ]
    assert SchedulingConstraints.validate_shift_transitions(night_shifts, test_resident) == True

    # Test consecutive day shifts
    day_shifts = [
        Shift(
            date=base_date + timedelta(days=i),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        ) for i in range(3)
    ]
    assert SchedulingConstraints.validate_shift_transitions(day_shifts, test_resident) == True

def test_validate_pto_single_day(self, test_resident, base_date):
    """Test that resident isn't scheduled during single day PTO"""
    # Add PTO for the test resident
    test_resident.time_off = [
        TimeOff(
            start_date=base_date + timedelta(days=1),
            end_date=base_date + timedelta(days=1),
            is_pto=True
        )
    ]
    
    # Try to schedule a shift during PTO
    shifts = [
        Shift(
            date=base_date + timedelta(days=1),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        )
    ]
    assert SchedulingConstraints.validate_time_off(shifts, test_resident) == False

def test_validate_pto_multiple_days(self, test_resident, base_date):
    """Test that resident isn't scheduled during multi-day PTO"""
    # Add PTO for the test resident
    test_resident.time_off = [
        TimeOff(
            start_date=base_date + timedelta(days=1),
            end_date=base_date + timedelta(days=3),
            is_pto=True
        )
    ]
    
    # Try to schedule shifts before, during, and after PTO
    shifts = [
        # Before PTO (valid)
        Shift(
            date=base_date,
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        ),
        # During PTO (invalid)
        Shift(
            date=base_date + timedelta(days=2),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        ),
        # After PTO (valid)
        Shift(
            date=base_date + timedelta(days=4),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        )
    ]
    assert SchedulingConstraints.validate_time_off(shifts, test_resident) == False

def test_validate_rto_same_as_pto(self, test_resident, base_date):
    """Test that RTO is treated the same as PTO for scheduling"""
    # Add RTO for the test resident
    test_resident.time_off = [
        TimeOff(
            start_date=base_date + timedelta(days=1),
            end_date=base_date + timedelta(days=1),
            is_pto=False  # RTO
        )
    ]
    
    # Try to schedule a shift during RTO
    shifts = [
        Shift(
            date=base_date + timedelta(days=1),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        )
    ]
    assert SchedulingConstraints.validate_time_off(shifts, test_resident) == False

def test_validate_no_time_off_conflicts(self, test_resident, base_date):
    """Test that scheduling works normally when there's no time off conflict"""
    # Add PTO for later dates
    test_resident.time_off = [
        TimeOff(
            start_date=base_date + timedelta(days=10),
            end_date=base_date + timedelta(days=12),
            is_pto=True
        )
    ]
    
    # Schedule shifts not during PTO
    shifts = [
        Shift(
            date=base_date + timedelta(days=i),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        )
        for i in range(3)  # Three shifts before PTO starts
    ]
    assert SchedulingConstraints.validate_time_off(shifts, test_resident) == True

    def test_five_pto_with_two_rto(self, test_resident, base_date):
    """Test the 5 PTO + 2 RTO scenario - should block all 7 days"""
    # Set up a 5-day PTO block followed by 2 RTO days
    test_resident.time_off = [
        TimeOff(
            start_date=base_date,
            end_date=base_date + timedelta(days=4),
            is_pto=True
        ),
        TimeOff(
            start_date=base_date + timedelta(days=5),
            end_date=base_date + timedelta(days=6),
            is_pto=False  # RTO
        )
    ]
    
    # Try to schedule shifts during the 7-day period
    shifts = [
        Shift(
            date=base_date + timedelta(days=i),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE,
            resident=test_resident
        )
        for i in range(7)  # Try scheduling all 7 days
    ]
    
    assert SchedulingConstraints.validate_time_off(shifts, test_resident) == False

def test_five_pto_shift_reduction(self, test_resident, base_date):
    """Test that 5 PTO days reduces shifts by 5 regardless of the 2 RTO days"""
    # Create a PGY2 resident (base 17 shifts)
    test_resident.level = ResidentLevel.PGY2
    
    # Set up a 5-day PTO block followed by 2 RTO days
    test_resident.time_off = [
        TimeOff(
            start_date=base_date,
            end_date=base_date + timedelta(days=4),
            is_pto=True
        ),
        TimeOff(
            start_date=base_date + timedelta(days=5),
            end_date=base_date + timedelta(days=6),
            is_pto=False  # RTO
        )
    ]
    
    # Should reduce from 17 to 12 shifts (17 base - 5 PTO days)
    assert test_resident.get_required_shifts(base_date.month, base_date.year) == 12

def test_chief_minimum_shifts(self, test_resident, base_date):
    """Test that chiefs can reduce to 10 shifts with PTO"""
    # Create a chief resident (base 15 shifts)
    test_resident.level = ResidentLevel.CHIEF
    
    # Set up 5 PTO days
    test_resident.time_off = [
        TimeOff(
            start_date=base_date,
            end_date=base_date + timedelta(days=4),
            is_pto=True
        )
    ]
    
    # Should reduce from 15 to 10 shifts
    assert test_resident.get_required_shifts(base_date.month, base_date.year) == 10