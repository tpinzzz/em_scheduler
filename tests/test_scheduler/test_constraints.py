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
        shifts = []
        for i in range(6):
            shift = Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE
        )
            shift.add_resident(test_resident)
            shifts.append(shift)
        
        assert SchedulingConstraints.validate_consecutive_shifts(shifts, test_resident) == True
    
    def test_validate_consecutive_shifts_over_limit(self, test_resident, base_date):
        """Test that more than 6 consecutive shifts is invalid"""
        # Create 7 consecutive day shifts
        shifts = []
        for i in range(7):
            shift = Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE
        )
            shift.add_resident(test_resident)
            shifts.append(shift)
        
        assert SchedulingConstraints.validate_consecutive_shifts(shifts, test_resident) == False
    
    def test_validate_consecutive_shifts_with_gap(self, test_resident, base_date):
        """Test that shifts with a gap reset the consecutive count"""
        # Create shifts with a gap: 3 shifts, 1 day gap, 3 more shifts

        shifts = []
        for i in [0, 1, 2, 4, 5, 6]:  # Note the gap at day 3
            shift = Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE
        )
            shift.add_resident(test_resident)  # ✅ Add resident after creating shift
            shifts.append(shift)

        
        assert SchedulingConstraints.validate_consecutive_shifts(shifts, test_resident) == True

    def test_validate_night_to_day_transition(self, test_resident, base_date):
        """Test transition from night shifts to day shifts requires 48h rest"""
        shifts = []
        night_shift = Shift(date=base_date, shift_type=ShiftType.NIGHT, pod=Pod.PURPLE)
        night_shift.add_resident(test_resident)
        shifts.append(night_shift)

        day_shift = Shift(date=base_date + timedelta(days=2), shift_type=ShiftType.DAY, pod=Pod.PURPLE)
        day_shift.add_resident(test_resident)
        shifts.append(day_shift)

        assert SchedulingConstraints.validate_shift_transitions(shifts, test_resident) == False

    def test_validate_night_to_day_transition_valid(self, test_resident, base_date):
        """Test valid transition from night shifts to day shifts with 48h rest"""
        shifts = []
        
        # Block of night shifts
        night_shift = Shift(
            date=base_date,
            shift_type=ShiftType.NIGHT,
            pod=Pod.PURPLE
        )
        night_shift.add_resident(test_resident)  # ✅ Add resident after shift creation
        shifts.append(night_shift)

        # Starting day shifts after proper rest (48h after last night shift ends)
        day_shift = Shift(
            date=base_date + timedelta(days=3),  # Full 48h rest ensured
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE
        )
        day_shift.add_resident(test_resident)  # ✅ Add resident after shift creation
        shifts.append(day_shift)

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
                date=base_date + timedelta(days=1),  # This is too soon
                shift_type=ShiftType.NIGHT,
                pod=Pod.PURPLE,
                resident=test_resident
            )
        ]
        assert SchedulingConstraints.validate_shift_transitions(shifts, test_resident) == False

    def test_validate_day_to_night_transition(self, test_resident, base_date):
        """Test transition from day shifts to night shifts requires 48h rest"""
        shifts = []

        # Block of day shifts
        day_shift = Shift(
            date=base_date,
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE
        )
        day_shift.add_resident(test_resident)  # ✅ Add resident after shift creation
        shifts.append(day_shift)

        # Trying to start night shifts too soon
        night_shift = Shift(
            date=base_date + timedelta(days=1),  # This is too soon
            shift_type=ShiftType.NIGHT,
            pod=Pod.PURPLE
        )
        night_shift.add_resident(test_resident)  # ✅ Add resident after shift creation
        shifts.append(night_shift)

        assert SchedulingConstraints.validate_shift_transitions(shifts, test_resident) == False

    def test_consecutive_night_shifts_valid(self, test_resident, base_date):
        """Test that consecutive night shifts are allowed"""
        night_shifts = []
        for i in range(3):
            shift = Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.NIGHT,
                pod=Pod.PURPLE
            )
            shift.add_resident(test_resident)  # ✅ Assign resident after shift creation
            night_shifts.append(shift)

        assert SchedulingConstraints.validate_shift_transitions(night_shifts, test_resident) == True


    def test_consecutive_day_shifts_valid(self, test_resident, base_date):
        """Test that consecutive day shifts are allowed"""
        day_shifts = []
        for i in range(3):
            shift = Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE
            )
            shift.add_resident(test_resident)  # ✅ Assign resident after shift creation
            day_shifts.append(shift)

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
        shifts = []
        shift = Shift(
            date=base_date + timedelta(days=1),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE
        )
        shift.add_resident(test_resident)  # ✅ Add resident after shift creation
        shifts.append(shift)

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
        shifts = []
        for day_offset in [0, 2, 4]:  # Only include allowed shifts
            shift = Shift(
                date=base_date + timedelta(days=day_offset),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE
            )
            shift.add_resident(test_resident)
            shifts.append(shift)

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
        shifts = []
        shift = Shift(
            date=base_date + timedelta(days=1),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE
        )
        shift.add_resident(test_resident)  # ✅ Add resident after shift creation
        shifts.append(shift)

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
        shifts = []
        for i in range(3):  # Three shifts before PTO starts
            shift = Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE
            )
            shift.add_resident(test_resident)  # ✅ Add resident after shift creation
            shifts.append(shift)

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
        shifts = []
        for i in range(7):  # Try scheduling all 7 days
            shift = Shift(
                date=base_date + timedelta(days=i),
                shift_type=ShiftType.DAY,
                pod=Pod.PURPLE
            )
            shift.add_resident(test_resident)  # ✅ Add resident after shift creation
            shifts.append(shift)

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


class TestShiftClass:
    @pytest.fixture
    def test_pgy1(self):
        """Create a test PGY1 resident"""
        return Resident(
            id="PGY1001",
            name="Test PGY1",
            level=ResidentLevel.PGY1,
            pod_preferences=[Pod.PURPLE, Pod.ORANGE],
            time_off=[]
        )
    
    @pytest.fixture
    def test_pgy3(self):
        """Create a test PGY3 resident"""
        return Resident(
            id="PGY3001",
            name="Test PGY3",
            level=ResidentLevel.PGY3,
            pod_preferences=[Pod.PURPLE, Pod.ORANGE],
            time_off=[]
        )
    
    @pytest.fixture
    def test_shift(self):
        """Create a test shift"""
        return Shift(
            date=datetime(2025, 2, 1),
            shift_type=ShiftType.DAY,
            pod=Pod.PURPLE
        )
    
    def test_add_resident(self, test_shift, test_pgy1):
        """Test adding a resident to a shift"""
        test_shift.add_resident(test_pgy1)
        assert len(test_shift.residents) == 1
        assert test_shift.residents[0] == test_pgy1
        
        # Test adding same resident twice doesn't duplicate
        test_shift.add_resident(test_pgy1)
        assert len(test_shift.residents) == 1
    
    def test_remove_resident(self, test_shift, test_pgy1, test_pgy3):
        """Test removing a resident from a shift"""
        test_shift.add_resident(test_pgy1)
        test_shift.add_resident(test_pgy3)
        
        test_shift.remove_resident(test_pgy1)
        assert len(test_shift.residents) == 1
        assert test_pgy1 not in test_shift.residents
        assert test_pgy3 in test_shift.residents
        
        # Test removing non-existent resident doesn't error
        test_shift.remove_resident(test_pgy1)
        assert len(test_shift.residents) == 1
    
    def test_get_resident_levels(self, test_shift, test_pgy1, test_pgy3):
        """Test getting list of resident levels"""
        test_shift.add_resident(test_pgy1)
        test_shift.add_resident(test_pgy3)
        
        levels = test_shift.get_resident_levels()
        assert ResidentLevel.PGY1 in levels
        assert ResidentLevel.PGY3 in levels
        assert len(levels) == 2
    
    def test_has_supervision(self, test_shift, test_pgy1, test_pgy3):
        """Test supervision checking logic"""
        # Empty shift should return True (no PGY1 to supervise)
        assert test_shift.has_supervision() == True
        
        # PGY1 alone should return False
        test_shift.add_resident(test_pgy1)
        assert test_shift.has_supervision() == False
        
        # PGY1 with PGY3 should return True
        test_shift.add_resident(test_pgy3)
        assert test_shift.has_supervision() == True
        
        # PGY3 alone should return True
        test_shift.remove_resident(test_pgy1)
        assert test_shift.has_supervision() == True
    
    def test_count_residents_by_level(self, test_shift, test_pgy1, test_pgy3):
        """Test counting residents by level"""
        # Empty shift
        counts = test_shift.count_residents_by_level()
        assert len(counts) == 0
        
        # Add one of each
        test_shift.add_resident(test_pgy1)
        test_shift.add_resident(test_pgy3)
        counts = test_shift.count_residents_by_level()
        assert counts[ResidentLevel.PGY1] == 1
        assert counts[ResidentLevel.PGY3] == 1
        
        # Add another PGY1
        another_pgy1 = Resident(
            id="PGY1002",
            name="Another PGY1",
            level=ResidentLevel.PGY1,
            pod_preferences=[Pod.PURPLE, Pod.ORANGE],
            time_off=[]
        )
        test_shift.add_resident(another_pgy1)
        counts = test_shift.count_residents_by_level()
        assert counts[ResidentLevel.PGY1] == 2
        assert counts[ResidentLevel.PGY3] == 1