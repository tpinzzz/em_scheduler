from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import List, Optional, Dict

class Pod(Enum):
    PURPLE = "purple"  # Higher acuity
    ORANGE = "orange"  # Urgent care

class ShiftType(Enum):
    DAY = "day"       # 7 AM - 7 PM
    NIGHT = "night"   # 7 PM - 7 AM
    SWING = "swing"   # 11 AM - 11 PM

class ResidentLevel(Enum):
    PGY1 = "pgy1"
    PGY2 = "pgy2"
    PGY3 = "pgy3"
    CHIEF ="chief"
    TY = "ty" # Transitional Year
    FM_PGY1 = "fm_pgy1" # Family Medicine First Year
    FM_PGY2 = "fm_pgy2" # Family Medicine Second Year
    IM_PGY1 = "im_pgy1" # Internal Medicine First Year

@dataclass
class TimeOff:
    start_date: datetime
    end_date: datetime
    is_pto: bool  # True for PTO, False for RTO

@dataclass
class Resident:
    id: str
    name: str
    level: ResidentLevel
    pod_preferences: List[Pod]
    time_off: List[TimeOff]
    
    def get_required_shifts(self, month: int, year: int) -> int:
        """
        Calculate the required number of shifts for a resident in a given month.

        PTO Rules:
        - PTO reduces shifts one-for-one up to 5 days maximum
        - When 5 PTO days are taken, resident gets 2 additional RTO days (7 days total off)
        - Cannot reduce below minimum required shifts for their level
        
        Base Shift Requirements:
        - PGY1, PGY2: 17 shifts (minimum 12 with PTO)
        - PGY3: 16 shifts (minimum 11 with PTO)
        - CHIEF: 15 shifts (minimum 10 with PTO)
        - TY: 10 shifts (no reduction)
        - FM_PGY1: 13 shifts (no reduction)
        - FM_PGY2: 10 shifts (no reduction)
        - IM_PGY1: 12 shifts (no reduction)

        Args:
            month (int): Month to calculate shifts for (1-12)
            year (int): Year to calculate shifts for

        Returns:
            int: Number of required shifts for the month after applying PTO reductions
        """

        base_shifts = {
            ResidentLevel.PGY1: 17,
            ResidentLevel.PGY2: 17,
            ResidentLevel.PGY3: 16,
            ResidentLevel.CHIEF: 15, 
            ResidentLevel.TY: 10,      # Updated from 13 to 10
            ResidentLevel.FM_PGY1: 13, # Family Medicine First Years
            ResidentLevel.FM_PGY2: 10, # Family Medicine Second Years
            ResidentLevel.IM_PGY1: 12  # Internal Medicine First Years
        }
        
        minimum_shifts = {
            ResidentLevel.PGY1: 12,
            ResidentLevel.PGY2: 12,
            ResidentLevel.PGY3: 11,
            ResidentLevel.CHIEF: 10,  
            ResidentLevel.TY: base_shifts[ResidentLevel.TY],          # No reduction
            ResidentLevel.FM_PGY1: base_shifts[ResidentLevel.FM_PGY1], # No reduction
            ResidentLevel.FM_PGY2: base_shifts[ResidentLevel.FM_PGY2], # No reduction
            ResidentLevel.IM_PGY1: base_shifts[ResidentLevel.IM_PGY1]  # No reduction

        }

        # Calculate PTO days in the month
        pto_days = sum(
            (to.end_date - to.start_date).days + 1
            for to in self.time_off
            if to.is_pto and to.start_date.month == month and to.start_date.year == year
        )
        
        # Calculate shift reduction (1:1 reduction, max 5 shifts)
        shift_reduction = min(pto_days, 5)
        
        # Calculate required shifts after PTO
        required_shifts = base_shifts[self.level] - shift_reduction
        
        # Ensure we don't go below minimum
        return max(required_shifts, minimum_shifts[self.level])

@dataclass
class Shift:
    date: datetime
    shift_type: ShiftType
    pod: Pod
    resident: Optional[Resident] = None