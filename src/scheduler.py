from typing import List, Dict
from datetime import datetime, timedelta
from src.models import *

class SchedulingConstraints:
    MAX_CONSECUTIVE_SHIFTS = 6
    SHIFT_TRANSITION_REST_HOURS = 48  # Default rest period
    
    @staticmethod
    def validate_consecutive_shifts(schedule: List[Shift], resident: Resident) -> bool:
        """
        Validates that a resident is not scheduled for more than MAX_CONSECUTIVE_SHIFTS in a row.
        
        Args:
            schedule: List of all shifts in the schedule
            resident: The resident to check
            
        Returns:
            bool: True if the constraint is satisfied, False otherwise
        """
        # Get all shifts for this resident, sorted by date
        resident_shifts = sorted(
            [shift for shift in schedule if shift.resident == resident],
            key=lambda x: x.date
        )
        
        if not resident_shifts:
            return True
            
        # Check for consecutive shifts
        consecutive_count = 1
        for i in range(1, len(resident_shifts)):
            current_shift = resident_shifts[i]
            previous_shift = resident_shifts[i-1]
            
            # If shifts are on consecutive days
            if (current_shift.date - previous_shift.date).days == 1:
                consecutive_count += 1
                if consecutive_count > SchedulingConstraints.MAX_CONSECUTIVE_SHIFTS:
                    return False
            else:
                consecutive_count = 1
                
        return True

    @staticmethod
    def validate_shift_transitions(schedule: List[Shift], resident: Resident) -> bool:
        """
        Validates that proper rest periods are maintained when transitioning between shift types.
        
        Rules:
        - When transitioning from night shifts to day shifts, need 48 hours from end of last
          night shift (7am) to start of first day shift (7am)
        - When transitioning from day shifts to night shifts, need 48 hours from end of last
          day shift (7pm) to start of first night shift (7pm)
        """
        # Get all shifts for this resident, sorted by date
        resident_shifts = sorted(
            [shift for shift in schedule if shift.resident == resident],
            key=lambda x: x.date
        )
        
        for i in range(len(resident_shifts)-1):
            current_shift = resident_shifts[i]
            next_shift = resident_shifts[i+1]
            
            # Only check when shift types are different
            if current_shift.shift_type != next_shift.shift_type:
                
                # Calculate shift end and start times
                if current_shift.shift_type == ShiftType.NIGHT:
                    # Night shift ends at 7am next day
                    current_shift_end = current_shift.date + timedelta(days=1, hours=7)
                    next_shift_start = next_shift.date + timedelta(hours=7)  # Day shift starts at 7am
                else:  # current_shift is DAY
                    # Day shift ends at 7pm
                    current_shift_end = current_shift.date + timedelta(hours=19)
                    next_shift_start = next_shift.date + timedelta(hours=19)  # Night shift starts at 7pm
                
                hours_between = (next_shift_start - current_shift_end).total_seconds() / 3600
                
                if hours_between < SchedulingConstraints.SHIFT_TRANSITION_REST_HOURS:
                    return False
                    
        return True
    
    @staticmethod
    def validate_time_off(schedule: List[Shift], resident: Resident) -> bool:
        """
        Validates that a resident is not scheduled during their time off periods.
        Both PTO (Paid Time Off) and RTO (Required Time Off) are treated the same.
        
        Args:
            schedule: List of all shifts in the schedule
            resident: The resident to check
            
        Returns:
            bool: True if no shifts are scheduled during time off, False otherwise
        """
        # Get all shifts for this resident
        resident_shifts = [shift for shift in schedule if shift.resident == resident]
        
        # Check each shift against all time off periods
        for shift in resident_shifts:
            for time_off in resident.time_off:
                # A shift conflicts if it's on any day within the time off period
                if (time_off.start_date.date() <= shift.date.date() <= 
                    time_off.end_date.date()):
                    return False
                    
        return True

class Scheduler:
    def __init__(self, residents: List[Resident], month: int, year: int):
        self.residents = residents
        self.month = month
        self.year = year
        self.constraints = SchedulingConstraints()
        
    def generate_schedule(self) -> List[Shift]:
        """
        Main scheduling algorithm using constraint satisfaction.
        Returns a list of shifts with assigned residents.
        """
        schedule = self._initialize_empty_schedule()
        
        # Use Google OR-Tools for constraint satisfaction
        solver = self._setup_solver()
        solution = self._solve_constraints(solver)
        
        if solution:
            return self._convert_solution_to_schedule(solution)
        else:
            raise ValueError("No valid schedule found satisfying all constraints")
    
    def _initialize_empty_schedule(self) -> List[Shift]:
        """Creates empty shifts for the month based on requirements."""
        schedule = []
        current_date = datetime(self.year, self.month, 1)
        
        while current_date.month == self.month:
            # Skip Tuesday nights
            if current_date.weekday() != 1:  # Tuesday is 1
                for pod in Pod:
                    for shift_type in ShiftType:
                        if shift_type != ShiftType.SWING:  # Handle swing shifts separately
                            schedule.append(Shift(current_date, shift_type, pod))
            
            current_date += datetime.timedelta(days=1)
        
        return schedule
    
    def _validate_schedule(self, schedule: List[Shift]) -> bool:
        """Validates the complete schedule against all constraints."""
        for resident in self.residents:
            if not self.constraints.validate_consecutive_shifts(schedule, resident):
                return False
            if not self.constraints.validate_shift_transitions(schedule, resident):
                return False
            if not self.constraints.validate_time_off(schedule, resident):
                return False
        return True