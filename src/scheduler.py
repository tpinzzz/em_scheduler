from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import calendar
from ortools.sat.python import cp_model
from src.models import *

class SchedulingConstraints:
    MAX_CONSECUTIVE_SHIFTS = 6
    SHIFT_TRANSITION_REST_HOURS = 48  # Default rest period

    @staticmethod
    def needs_supervision(resident: Resident, pod: Pod, month: int) -> bool:
        """
        Determines if a PGY1 resident needs supervision for the given pod.
        
        Rules:
        - PGY1s need supervision in all pods July-December
        - PGY1s need supervision in PURPLE pod January-June
        - PGY1s can work alone in ORANGE pod January-June
        - Other residents don't need supervision
        """
        if resident.level != ResidentLevel.PGY1:
            return False
            
        # Residency year starts in July
        is_first_half = month >= 7 and month <= 12
        
        # First half of year - need supervision everywhere
        if is_first_half:
            return True
        
        # Second half of year - only need supervision in PURPLE pod
        return pod == Pod.PURPLE
    
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
            [shift for shift in schedule if resident in shift.residents],
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
            [shift for shift in schedule if resident in shift.residents],
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
        resident_shifts = [shift for shift in schedule if resident in shift.residents]
        
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

    def _setup_solver(self) -> Tuple[cp_model.CpModel, cp_model.CpSolver, Dict]:
        """
        Sets up the CP-SAT solver with variables and constraints for the schedule.
        Returns the model, solver, and shift variables.
        """
        model = cp_model.CpModel()
        empty_schedule = self._initialize_empty_schedule()

        print("\nInitial Setup:")
        print(f"Total shifts to fill: {len(empty_schedule)}")
        total_required = sum(resident.get_required_shifts(self.month, self.year) 
                            for resident in self.residents)
        print(f"Total shifts required by residents: {total_required}")

        # Create variables: binary variable for each (resident, shift) pair
        shifts = {}
        for r_idx, resident in enumerate(self.residents):
            shifts[r_idx] = {}
            for shift in empty_schedule:
                shift_key = (shift.date.day, shift.shift_type, shift.pod)
                shifts[r_idx][shift_key] = model.NewBoolVar(
                    f'shift_r{r_idx}_d{shift.date.day}_t{shift.shift_type.value}_p{shift.pod.value}'
                )

        # Each shift must have exactly one resident
        print("\nShift Coverage Requirements:")
        shift_count = 0
        for shift in empty_schedule:
            shift_key = (shift.date.day, shift.shift_type, shift.pod)
            model.Add(sum(shifts[r_idx][shift_key] 
                for r_idx in range(len(self.residents))) <= 1)
            shift_count += 1
        print(f"Allowing 0-1 residents for {shift_count} shifts")

        # Each resident must work their exact required shifts
        print("\nResident Shift Requirements:")
        for r_idx, resident in enumerate(self.residents):
            required_shifts = resident.get_required_shifts(self.month, self.year)
            total_shifts = sum(shifts[r_idx].values())
            model.Add(total_shifts == required_shifts)
            print(f"{resident.name} ({resident.level.value}): Must work exactly {required_shifts} shifts")

        # PGY1 supervision constraint
        pgy1s = [r for r in self.residents if r.level == ResidentLevel.PGY1]
        if pgy1s:
            print("\nPGY1 Supervision Requirements:")
            for pgy1 in pgy1s:
                needs_purple = self.constraints.needs_supervision(pgy1, Pod.PURPLE, self.month)
                needs_orange = self.constraints.needs_supervision(pgy1, Pod.ORANGE, self.month)
                print(f"{pgy1.name}: Needs supervision - Purple: {needs_purple}, Orange: {needs_orange}")
        
        for shift in empty_schedule:
            shift_key = (shift.date.day, shift.shift_type, shift.pod)
            for r_idx, resident in enumerate(self.residents):
                if resident.level == ResidentLevel.PGY1:
                    if self.constraints.needs_supervision(resident, shift.pod, self.month):
                        supervisors = sum(
                            shifts[other_idx][shift_key]
                            for other_idx, other_resident in enumerate(self.residents)
                            if other_resident.level != ResidentLevel.PGY1
                        )
                        # If PGY1 is assigned, there must be a supervisor
                        model.Add(supervisors >= shifts[r_idx][shift_key])

        # Each resident can only work one shift per day
        for r_idx in range(len(self.residents)):
            for day in range(1, calendar.monthrange(self.year, self.month)[1] + 1):
                day_shifts = [
                    shifts[r_idx][key]
                    for key in shifts[r_idx].keys()
                    if key[0] == day
                ]
                if day_shifts:
                    model.Add(sum(day_shifts) <= 1)

        print("\nSolver Configuration:")
        print(f"Setting up solver with {len(self.residents)} residents")
        for resident in self.residents:
            required = resident.get_required_shifts(self.month, self.year)
            print(f"Resident {resident.name} requires {required} shifts")

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60

        return model, solver, shifts


    def _convert_solution_to_schedule(self, solver: cp_model.CpSolver, shift_vars: Dict, empty_schedule: List[Shift]) -> List[Shift]:
        """
        Converts the OR-Tools solution into a list of assigned Shift objects.
        """
        assigned_schedule = []

        ##DEBUGGING CODE BEGINS
        for shift in empty_schedule:
            shift_key = (shift.date.day, shift.shift_type, shift.pod)
            assigned_resident = None

            for r_idx, resident in enumerate(self.residents):
                if shift_key in shift_vars[r_idx]:  # Ensure key exists
                    if solver.Value(shift_vars[r_idx][shift_key]) == 1:
                        assigned_resident = resident
                        break  # Assign only one resident per shift

            if assigned_resident:
                print(f"✅ {shift.date} - {shift.shift_type} - {shift.pod} assigned to {assigned_resident.name}")
            else:
                print(f"⚠️ Unstaffed shift: {shift.date}, {shift.shift_type}, {shift.pod}")
        ##DEBUGGING CODE ENDS

        for shift in empty_schedule:
            shift_key = (shift.date.day, shift.shift_type, shift.pod)
            assigned_resident = None
            
            for r_idx, resident in enumerate(self.residents):
                if solver.Value(shift_vars[r_idx][shift_key]) == 1:
                    assigned_resident = resident
                    break  # Assign only one resident per shift

            if assigned_resident:
                new_shift = Shift(
                    date=shift.date,
                    shift_type=shift.shift_type,
                    pod=shift.pod
                )
                new_shift.add_resident(assigned_resident)
                assigned_schedule.append(new_shift)
            else:
                ##DEBUGGING STATEMENT BELOW REPLACED raise ValueError for now
                #raise ValueError(f"Unstaffed shift detected: {shift.date}, {shift.shift_type}, {shift.pod}")
                print(f"Unstaffed shift: {shift.date}, {shift.shift_type}, {shift.pod}")
        return assigned_schedule


    def generate_schedule(self) -> List[Shift]:
        """
        Main scheduling algorithm using constraint satisfaction.
        Returns a list of shifts with assigned residents.
        """
        empty_schedule = self._initialize_empty_schedule()
        
        # Use Google OR-Tools for constraint satisfaction
        model, solver, shift_vars = self._setup_solver()
        status = solver.Solve(model)  # Status check

        # Debugging: Solver status
        print(f"Solver status: {status}")

        if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
            print("❌ No feasible solution found! Debugging constraint issues...")
            
            # Print required shifts per resident
            for resident in self.residents:
                required_shifts = resident.get_required_shifts(self.month, self.year)
                print(f"Resident {resident.name} requires {required_shifts} shifts")

            return []  # Prevent crash, return empty schedule

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            # Generate the schedule
            schedule = self._convert_solution_to_schedule(solver, shift_vars, empty_schedule)

            # Calculate staffed vs. unstaffed shifts
            num_staffed = sum(1 for shift in schedule if shift.resident)
            num_unstaffed = sum(1 for shift in schedule if not shift.resident)

            # Debugging: Shift statistics
            print(f"✅ Staffed Shifts: {num_staffed}")
            print(f"⚠️ Unstaffed Shifts: {num_unstaffed}")

            # Count shifts per resident
            resident_shift_counts = {resident.name: 0 for resident in self.residents}
            for shift in schedule:
                if shift.resident:
                    resident_shift_counts[shift.resident.name] += 1

            print("\n📊 Resident Shift Analysis:")
            for resident in self.residents:
                required_shifts = resident.get_required_shifts(self.month, self.year)
                assigned_shifts = resident_shift_counts.get(resident.name, 0)
                print(f"🧑‍⚕️ {resident.name}: Required {required_shifts}, Assigned {assigned_shifts}")

            return schedule
        
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
            
            current_date += timedelta(days=1)

        print(f"Total available shifts: {len(schedule)}")
        
        return schedule
    
    def _validate_schedule(self, schedule: List[Shift]) -> bool:
        """Validates the complete schedule against all constraints."""
        for residents in self.residents:
            if not self.constraints.validate_consecutive_shifts(schedule, residents):
                return False
            if not self.constraints.validate_shift_transitions(schedule, residents):
                return False
            if not self.constraints.validate_time_off(schedule, residents):
                return False
        return True