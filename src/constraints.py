# constraints.py (new file)
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from ortools.sat.python import cp_model

# Try package-level import first, then local import
try:
    from src.models import *
except ImportError:
    from models import *

class SchedulingConstraints:
    """
    Adds constraints to the CP-SAT model during initialization.
    These are enforced during the solving process.
    """
    
    @staticmethod
    def add_buddy_constraints(model: cp_model.CpModel, shifts: Dict, 
                            residents: List[Resident], empty_schedule: List[Shift], 
                            block_number: int):
        """
        Adds buddy system constraints for Block 1:
        - Swing shifts can only be filled by PGY2 residents
        - Ensures PGY1 residents have a PGY3 buddy during the first 10 days
        """
        # Only enforce in Block 1
        if block_number != 1:
            return
            
        # Add constraints for early shifts (first 10 days)
        early_shifts = []
        for shift in empty_schedule:
            if (shift.date - shift.date.replace(day=1)).days < 10 and shift.shift_type != ShiftType.SWING:
                early_shifts.append(shift)
        
        # Sort shifts chronologically
        early_shifts.sort(key=lambda s: (s.date, s.shift_type.value))
        
        for shift in empty_schedule:
            shift_key = (shift.date.day, shift.shift_type, shift.pod)
            
            # Get all resident variables for this shift
            resident_vars = []
            for r_idx, resident in enumerate(residents):
                if shift_key in shifts[r_idx]:
                    resident_vars.append((r_idx, resident))
            
            # Handle swing shifts (only PGY2 allowed in Block 1)
            if shift.shift_type == ShiftType.SWING:
                for r_idx, resident in resident_vars:
                    if resident.level != ResidentLevel.PGY2:
                        model.Add(shifts[r_idx][shift_key] == 0)
                continue
            
            # For early shifts, ensure PGY1s always have a PGY3 buddy
            if shift in early_shifts:
                # Count PGY1 and PGY3 variables for this shift
                pgy1_vars = [shifts[r_idx][shift_key] 
                            for r_idx, resident in resident_vars 
                            if resident.level == ResidentLevel.PGY1]
                            
                pgy3_vars = [shifts[r_idx][shift_key] 
                            for r_idx, resident in resident_vars 
                            if resident.level == ResidentLevel.PGY3]
                
                # If there are PGY1s and PGY3s available for this shift
                if pgy1_vars and pgy3_vars:
                    # For each PGY1 working, require at least one PGY3
                    model.Add(sum(pgy3_vars) >= sum(pgy1_vars))

    
    @staticmethod
    def add_side_allocation_constraints(model: cp_model.CpModel, shifts: Dict,
                                    residents: List[Resident], empty_schedule: List[Shift],
                                    block_number: int):
        """Adds side allocation constraints to the model."""
        # Set max residents based on block number
        max_residents_per_side = 4 if block_number == 1 else 3
        
        # Group shifts by day and pod
        for shift in empty_schedule:
            # Skip swing shifts - they're handled separately
            if shift.shift_type == ShiftType.SWING:
                continue
                
            shift_key = (shift.date.day, shift.shift_type, shift.pod)
            
            # Count all residents for this shift
            resident_count_vars = []
            for r_idx in range(len(residents)):
                if shift_key in shifts[r_idx]:
                    resident_count_vars.append(shifts[r_idx][shift_key])
            
            # Maximum residents per side
            if resident_count_vars:
                model.Add(sum(resident_count_vars) <= max_residents_per_side)
        
        # Handle swing shifts - max 1 resident per swing shift
        for shift in empty_schedule:
            if shift.shift_type == ShiftType.SWING:
                shift_key = (shift.date.day, shift.shift_type, shift.pod)
                
                resident_count_vars = []
                for r_idx in range(len(residents)):
                    if shift_key in shifts[r_idx]:
                        resident_count_vars.append(shifts[r_idx][shift_key])
                
                if resident_count_vars:
                    model.Add(sum(resident_count_vars) <= 1)


    
    @staticmethod
    def add_pto_constraints(model: cp_model.CpModel, shifts: Dict,
                        residents: List[Resident], block: Block):
        """Adds PTO blocking constraints to the model."""
        for r_idx, resident in enumerate(residents):
            if not resident.time_off:
                continue
                
            pto_periods = [to for to in resident.time_off if to.is_pto]
            
            for pto in pto_periods:
                start_date = pto.start_date.date()
                end_date = pto.end_date.date()
                
                current_date = start_date
                while current_date <= end_date:
                    if block.start_date.date() <= current_date <= block.end_date.date():
                        for pod in Pod:
                            for shift_type in ShiftType:
                                shift_key = (current_date.day, shift_type, pod)
                                if shift_key in shifts[r_idx]:
                                    model.Add(shifts[r_idx][shift_key] == 0)
                    current_date += timedelta(days=1)