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
        
        # Calculate PTO reduction
        pto_days = sum(
            (to.end_date - to.start_date).days + 1
            for to in self.time_off
            if to.is_pto and to.start_date.month == month and to.start_date.year == year
        )
        
        # Apply PTO reduction rules
        if pto_days >= 5:
            shift_reduction = 5  # Maximum reduction for 5+ consecutive days
        else:
            shift_reduction = pto_days
            
        return base_shifts[self.level] - shift_reduction

@dataclass
class Shift:
    date: datetime
    shift_type: ShiftType
    pod: Pod
    resident: Optional[Resident] = None