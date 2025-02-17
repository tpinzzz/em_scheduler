from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict

class RotationType(Enum):
    ER = "er"
    ICU = "icu"
    PEDS = "peds"
    ELECTIVE = "elective"
    OTHER = "other"


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
class Block:
    number: int  # 1-13
    start_date: datetime
    end_date: datetime
    
    @classmethod
    def get_block_dates(cls, block_number: int, academic_year: int) -> 'Block':
        """Calculate start and end dates for a given block number."""
        if block_number < 1 or block_number > 13:
            raise ValueError("Block number must be between 1 and 13")
        
        if block_number == 1:
            start_date = datetime(academic_year, 7, 1)
        else:
            prev_block = cls.get_block_dates(block_number - 1, academic_year)
            start_date = prev_block.end_date + timedelta(days=1)
            
        if block_number == 13:
            end_date = datetime(academic_year + 1, 6, 30)
        else:
            end_date = start_date + timedelta(days=27)  # 28 day blocks
                    
        return cls(block_number, start_date, end_date)

@dataclass
class Rotation:
    block_number: int
    rotation_type: RotationType
    is_flexible: bool

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
    rotations: Dict[int, Rotation] = field(default_factory=dict)  # block_number -> Rotation

    def can_work_transition_day(self, date: datetime, is_block_start: bool) -> bool:
        """Check if resident can work on a block transition day."""
        block = self.get_block_for_date(date)
        if not block:
            return False
            
        if is_block_start:
            current_rotation = self.rotations.get(block.number)
            prev_rotation = self.rotations.get(block.number - 1)
            return (current_rotation and prev_rotation and 
                    current_rotation.rotation_type == RotationType.ER and
                    prev_rotation.rotation_type == RotationType.ER)
        else:
            current_rotation = self.rotations.get(block.number)
            next_rotation = self.rotations.get(block.number + 1)
            return (current_rotation and next_rotation and
                    current_rotation.rotation_type == RotationType.ER and
                    next_rotation.rotation_type == RotationType.ER)
        
    def needs_pgy3_buddy(self, date: datetime) -> bool:
        """Check if PGY1 needs a PGY3 buddy (first 3 shifts in Block 1)."""
        if self.level != ResidentLevel.PGY1:
            return False
            
        block = self.get_block_for_date(date)
        if not block or block.number != 1:
            return False
            
        # Count previous shifts in Block 1
        return self.count_shifts_in_block(block) < 3
    
    def get_block_for_date(self, date: datetime) -> Optional[Block]:
        """Get the block containing the given date."""
        academic_year = date.year if date.month >= 7 else date.year - 1
        for block_num in range(1, 14):
            block = Block.get_block_dates(block_num, academic_year)
            if block.start_date <= date <= block.end_date:
                return block
        return None
    
    def count_shifts_in_block(self, block: Block) -> int:
        """Count number of shifts worked in a given block."""
        # This will need to be implemented based on how we track assigned shifts
        pass    
    
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
    residents: List[Resident] = field(default_factory=list)

    def add_resident(self, resident:Resident) -> None:
        """Add a resident to this shift."""
        if resident not in self.residents:
            self.residents.append(resident)

    def remove_resident(self, resident: Resident) -> None:
        """Remove a resident from this shift."""
        if resident in self.residents:
            self.residents.remove(resident)
    
    def get_resident_levels(self) -> List[ResidentLevel]:
        """Get list of resident levels working this shift."""
        return [resident.level for resident in self.residents]
    
    def has_supervision(self) -> bool:
        """Check if shift has appropriate supervision for PGY1s."""
        pgy1_present = ResidentLevel.PGY1 in self.get_resident_levels()
        supervisor_present = any(
            level in self.get_resident_levels() 
            for level in [ResidentLevel.PGY2, ResidentLevel.PGY3, ResidentLevel.CHIEF]
        )
        return not pgy1_present or (pgy1_present and supervisor_present)
    
    def count_residents_by_level(self) -> Dict[ResidentLevel, int]:
        """Count number of residents by training level."""
        counts = {}
        for resident in self.residents:
            counts[resident.level] = counts.get(resident.level, 0) + 1
        return counts