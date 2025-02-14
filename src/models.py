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
    OFF_SERVICE = "off_service"
    TY = "ty"
    CHIEF ="chief"

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
        base_shifts = {
            ResidentLevel.PGY1: 17,
            ResidentLevel.PGY2: 17,
            ResidentLevel.PGY3: 16,
            ResidentLevel.OFF_SERVICE: 13,
            ResidentLevel.TY: 13,
            ResidentLevel.CHIEF: 15 
        }
        
        minimum_shifts = {
            ResidentLevel.PGY1: 12,
            ResidentLevel.PGY2: 12,
            ResidentLevel.PGY3: 11,
            ResidentLevel.OFF_SERVICE: base_shifts[ResidentLevel.OFF_SERVICE],  # No reduction
            ResidentLevel.TY: base_shifts[ResidentLevel.TY],  # No reduction
            ResidentLevel.CHIEF: 10  # Need to confirm minimum
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