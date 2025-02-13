from typing import List, Dict
import datetime
from src.models import *

class SchedulingConstraints:
    MAX_CONSECUTIVE_SHIFTS = 6
    MIN_REST_HOURS = 48  # Default rest period
    MIN_REST_HOURS_MONDAY_NIGHT = 24  # Special case for Monday night to Wednesday day
    
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
        return True