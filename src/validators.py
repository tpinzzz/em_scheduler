from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from models import *  # Direct import since file is now at same level

class SchedulingValidator:
    @staticmethod
    def validate_buddy_system(shift: Shift, block_number: int) -> bool:
        """
        Validates the buddy system requirements for Block 1:
        - PGY1 residents must be paired with PGY3 residents
        - Swing shifts should only be filled by PGY2 residents
        
        Returns True if requirements are met, False otherwise.
        """
        # Only enforce buddy system in Block 1
        if block_number != 1:
            return True
            
        residents = shift.residents
        
        # Check swing shift restriction 
        if shift.shift_type == ShiftType.SWING:
            # In Block 1, swing shifts should only be filled by PGY2
            if not residents:  # Empty is okay for swing shifts
                return True
            # If filled, must be only PGY2
            return all(resident.level == ResidentLevel.PGY2 for resident in residents)
            
        # For regular shifts, check PGY1-PGY3 pairing
        has_pgy1 = any(r.level == ResidentLevel.PGY1 for r in residents)
        has_pgy3 = any(r.level == ResidentLevel.PGY3 for r in residents)
        
        # If there's a PGY1, there must be a PGY3
        if has_pgy1 and not has_pgy3:
            return False
            
        return True
    
    @staticmethod
    def validate_side_allocation(shifts_for_day: List[Shift], block_number: int) -> bool:
        """
        Validates the maximum number of residents per side (Purple/Orange):
        - Block 1: Maximum 4 residents per side
        - Other blocks: Maximum 3 residents per side
        - Swing shifts are handled separately (max 1 resident)
        
        Returns True if requirements are met, False otherwise.
        """
        purple_shifts = [s for s in shifts_for_day if s.pod == Pod.PURPLE and s.shift_type != ShiftType.SWING]
        orange_shifts = [s for s in shifts_for_day if s.pod == Pod.ORANGE and s.shift_type != ShiftType.SWING]
        
        # Get swing shifts separately
        purple_swing = [s for s in shifts_for_day if s.pod == Pod.PURPLE and s.shift_type == ShiftType.SWING]
        orange_swing = [s for s in shifts_for_day if s.pod == Pod.ORANGE and s.shift_type == ShiftType.SWING]
        
        # Count residents per side (excluding swing shifts)
        purple_residents = sum(len(s.residents) for s in purple_shifts)
        orange_residents = sum(len(s.residents) for s in orange_shifts)
        
        # Count swing shift residents
        purple_swing_residents = sum(len(s.residents) for s in purple_swing)
        orange_swing_residents = sum(len(s.residents) for s in orange_swing)
        
        # Set max residents based on block number
        max_residents_per_side = 4 if block_number == 1 else 3
        
        # Check if limits are exceeded
        if purple_residents > max_residents_per_side or orange_residents > max_residents_per_side:
            return False
            
        # Check swing shift limits (max 1 resident per swing shift)
        if purple_swing_residents > 1 or orange_swing_residents > 1:
            return False
            
        return True