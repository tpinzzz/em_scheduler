from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import calendar
from ortools.sat.python import cp_model
from models import * #was 'src.models' before because that worked.. Now just 'models' works not sure what the issue is. 
import logging

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
    def __init__(self, residents: List[Resident], block: Block):
        self.residents = residents
        self.block = block
        self.constraints = SchedulingConstraints()
        self.month = block.start_date.month
        self.year = block.start_date.year

    def _initialize_empty_schedule(self) -> List[Shift]:
        """Creates empty shifts for the block based on requirements."""
        schedule = []
        current_date = self.block.start_date
        
        logging.info(f'Initializing empty schedule for block {self.block.number}')

        while current_date <= self.block.end_date:
            logging.info(f"\nCreating shifts for {current_date.date()}")
            for pod in Pod:
                # Add required shifts (day and night)
                for shift_type in [ShiftType.DAY, ShiftType.NIGHT]:
                    # Skip Tuesday nights
                    if shift_type == ShiftType.NIGHT and current_date.weekday() == 1:
                        logging.debug(f"  Skipping Tuesday night for {pod.value}")
                        continue
                        
                    schedule.append(Shift(
                        date=current_date,
                        shift_type=shift_type,
                        pod=pod
                    ))
                    logging.debug(f"  Created {shift_type.value} shift for {pod.value} on {current_date.date()}")  # Added this line
                
                # Add optional swing shifts
                schedule.append(Shift(
                    date=current_date,
                    shift_type=ShiftType.SWING,
                    pod=pod
                ))
                logging.debug(f"  Created swing shift for {pod.value} on {current_date.date}")  # Added this line
            
            current_date += timedelta(days=1)
        
        logging.info(f"\nTotal shifts created: {len(schedule)}")  # Added this line
        return schedule


    
    def _setup_solver(self) -> Tuple[cp_model.CpModel, cp_model.CpSolver, Dict]:
        """
        Sets up the CP-SAT solver with variables and constraints for the schedule.
        Returns the model, solver, and shift variables.
        """
        model = cp_model.CpModel()
        empty_schedule = self._initialize_empty_schedule()

        logging.info("Initial Setup:")
        logging.info(f"Block {self.block.number}: {self.block.start_date.date()} to {self.block.end_date.date()}")
        logging.info(f"Total shifts to fill: {len(empty_schedule)}")

        # Create shift assignment variables
        shifts = {}
        logging.info("Creating shift variables:")
        
        # First create ALL variables
        for r_idx, resident in enumerate(self.residents):
            shifts[r_idx] = {}
            logging.info(f"Creating variables for {resident.name}:")
            for shift in empty_schedule:
                shift_key = (shift.date.day, shift.shift_type, shift.pod)
                shifts[r_idx][shift_key] = model.NewBoolVar(
                    f'shift_r{r_idx}_d{shift.date.day}_t{shift.shift_type.value}_p{shift.pod.value}'
                )
                
        # Then add constraints for who can't work
        for r_idx, resident in enumerate(self.residents):
            logging.info(f"Adding availability constraints for {resident.name}")
            for shift in empty_schedule:
                shift_key = (shift.date.day, shift.shift_type, shift.pod)
                
                # Check block transition days
                can_work = True
                if shift.date == self.block.start_date:
                    can_work = resident.can_work_transition_day(shift.date, True)
                    logging.debug(f"  Start day ({shift.date.date()}): can_work = {can_work}")
                elif shift.date == self.block.end_date:
                    can_work = resident.can_work_transition_day(shift.date, False)
                    logging.debug(f"  End day ({shift.date.date()}): can_work = {can_work}")
                
                # If they can't work, force the variable to 0
                if not can_work:
                    model.Add(shifts[r_idx][shift_key] == 0)
                    logging.debug(f"  Forcing {shift.date.date()} {shift.shift_type.value} {shift.pod.value} to 0")   

        # Add staffing requirements
        for shift in empty_schedule:
            shift_key = (shift.date.day, shift.shift_type, shift.pod)
            residents_for_shift = [shifts[r_idx][shift_key] for r_idx in range(len(self.residents))]
            
            if shift.shift_type == ShiftType.SWING:
                # Swing shifts can have 0 or more residents
                continue
            else:
                # Regular shifts need at least 1 resident
                model.Add(sum(residents_for_shift) >= 1)

        # Day/Night transition constraints 
        logging.info("Adding day/night transition constraints")
        for r_idx, resident in enumerate(self.residents):
            logging.info(f"Adding transition constraints for {resident.name}")
            
            # For each day in the block
            for day in range((self.block.end_date - self.block.start_date).days):
                current_date = self.block.start_date + timedelta(days=day)
                
                # For each shift type on current day
                for current_type in ShiftType:
                    # Check all pods for the current shift
                    for pod in Pod:
                        current_key = (current_date.day, current_type, pod)
                        if current_key not in shifts[r_idx]:
                            continue
                        
                        # Look ahead 5 days to check all possible transitions
                        for future_day in range(day, min(day + 5, (self.block.end_date - self.block.start_date).days)):
                            future_date = self.block.start_date + timedelta(days=future_day)
                            
                            # Check transitions to all shift types in all pods
                            for future_type in ShiftType:
                                if future_type != current_type:  # Only check different shift types
                                    for future_pod in Pod:  # Check all pods for future shifts
                                        future_key = (future_date.day, future_type, future_pod)
                                        if future_key not in shifts[r_idx]:
                                            continue
                                        
                                        # Calculate hours between shifts
                                        shift_times = {
                                            ShiftType.DAY: 7,    # 7am
                                            ShiftType.NIGHT: 19, # 7pm
                                            ShiftType.SWING: 11  # 11am
                                        }
                                        
                                        current_time = datetime.combine(current_date, 
                                            time(hour=shift_times[current_type]))
                                        future_time = datetime.combine(future_date, 
                                            time(hour=shift_times[future_type]))
                                        hours_between = (future_time - current_time).total_seconds() / 3600
                                        
                                        # If less than 48 hours between different types of shifts, prevent assignment
                                        if hours_between < 48:
                                            model.Add(shifts[r_idx][current_key] + shifts[r_idx][future_key] <= 1)
                                            
                                        # Add stricter constraints for certain transitions
                                        if ((current_type == ShiftType.NIGHT and future_type == ShiftType.DAY) or
                                            (current_type == ShiftType.DAY and future_type == ShiftType.NIGHT)):
                                            # Require at least 72 hours between day/night transitions
                                            if hours_between < 72:
                                                model.Add(shifts[r_idx][current_key] + shifts[r_idx][future_key] <= 1)


        # Prevent more than one shift type change in a 72-hour period
        for day in range((self.block.end_date - self.block.start_date).days - 3):
            current_date = self.block.start_date + timedelta(days=day)
            window_shifts = []
            for d in range(3):  # Look at 3-day windows
                for pod in Pod:
                    for shift_type in ShiftType:
                        key = (current_date.day + d, shift_type, pod)
                        if key in shifts[r_idx]:
                            window_shifts.append(shifts[r_idx][key])
            if window_shifts:
                model.Add(sum(window_shifts) <= 2)  # Maximum 2 shifts in any 3-day window
        # Add after the staffing requirements in _setup_solver:
        """
        # PGY1 supervision constraints
        for shift in empty_schedule:
            if shift.shift_type != ShiftType.SWING:  # Only enforce for regular shifts
                shift_key = (shift.date.day, shift.shift_type, shift.pod)
                
                # Get variables for PGY1s and supervisors for this shift
                pgy1_vars = []
                supervisor_vars = []
                
                for r_idx, resident in enumerate(self.residents):
                    if shift_key not in shifts[r_idx]:
                        continue
                        
                    if resident.level == ResidentLevel.PGY1:
                        pgy1_vars.append(shifts[r_idx][shift_key])
                    elif resident.level in [ResidentLevel.PGY2, ResidentLevel.PGY3, ResidentLevel.CHIEF]:
                        supervisor_vars.append(shifts[r_idx][shift_key])
                
                # If any PGY1 is working, require at least one supervisor
                if pgy1_vars and supervisor_vars:
                    for pgy1_var in pgy1_vars:
                        model.Add(sum(supervisor_vars) >= pgy1_var)

        # Consecutive shift limits
        for r_idx, resident in enumerate(self.residents):
            # For each day in the block
            for day in range((self.block.end_date - self.block.start_date).days + 1):
                current_date = self.block.start_date + timedelta(days=day)
                
                # Look at 6-day windows
                if day + 6 <= (self.block.end_date - self.block.start_date).days:
                    consecutive_vars = []
                    
                    # Collect all shifts in the 6-day window
                    for offset in range(6):
                        check_date = current_date + timedelta(days=offset)
                        for pod in Pod:
                            for shift_type in [ShiftType.DAY, ShiftType.NIGHT]:  # Exclude swing shifts
                                shift_key = (check_date.day, shift_type, pod)
                                if shift_key in shifts[r_idx]:
                                    consecutive_vars.append(shifts[r_idx][shift_key])
                    
                    # Ensure no more than 6 consecutive shifts
                    if consecutive_vars:
                        model.Add(sum(consecutive_vars) <= 6)
        

        # Add PGY1 buddy system constraint for Block 1
        if self.block.number == 1:
            pgy1s = [r for r in self.residents if r.level == ResidentLevel.PGY1]
            pgy3s = [r for r in self.residents if r.level == ResidentLevel.PGY3]
            
            for pgy1 in pgy1s:
                pgy1_idx = self.residents.index(pgy1)
                
                # For first 3 shifts of each PGY1
                first_three_shifts = []
                for shift in empty_schedule:
                    shift_key = (shift.date.day, shift.shift_type, shift.pod)
                    if shift_key in shifts[pgy1_idx]:
                        first_three_shifts.append(shift_key)
                        if len(first_three_shifts) == 3:
                            break
                
                # Require a PGY3 to be present for these shifts
                for shift_key in first_three_shifts:
                    pgy3_present = []
                    for pgy3 in pgy3s:
                        pgy3_idx = self.residents.index(pgy3)
                        if shift_key in shifts[pgy3_idx]:
                            pgy3_present.append(shifts[pgy3_idx][shift_key])
                    
                    if pgy3_present:
                        # If PGY1 is working, one PGY3 must be present
                        model.Add(sum(pgy3_present) >= shifts[pgy1_idx][shift_key]) 
        """
        # Each resident must work their exact required shifts
        print("\nResident Shift Requirements:")
        for r_idx, resident in enumerate(self.residents):
            required_shifts = resident.get_required_shifts(
                self.block.start_date.month,
                self.block.start_date.year
            )
            total_shifts = sum(shifts[r_idx].values())
            model.Add(total_shifts == required_shifts)
            print(f"{resident.name} ({resident.level.value}): Must work exactly {required_shifts} shifts")

        # Each resident can only work one shift per day
        for r_idx in range(len(self.residents)):
            block_days = (self.block.end_date - self.block.start_date).days + 1
            for day in range(block_days):
                current_date = self.block.start_date + timedelta(days=day)
                shifts_on_this_day = [
                    shifts[r_idx][key]
                    for key in shifts[r_idx].keys()
                    if key[0] == current_date.day  # we use current_date.day here
                ]
                if shifts_on_this_day:
                    model.Add(sum(shifts_on_this_day) <= 1)

        print("\nSolver Configuration:")
        print(f"Setting up solver for Block {self.block.number}")
        print(f"Date Range: {self.block.start_date.date()} to {self.block.end_date.date()}")
        print(f"Setting up solver with {len(self.residents)} residents")
        for resident in self.residents:
            required = resident.get_required_shifts(
                self.block.start_date.month,
                self.block.start_date.year
            )
            print(f"Resident {resident.name} requires {required} shifts")

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60

        return model, solver, shifts


    def _convert_solution_to_schedule(self, solver: cp_model.CpSolver, shift_vars: Dict, empty_schedule: List[Shift]) -> List[Shift]:
        """
        Converts the OR-Tools solution into a list of assigned Shift objects.
        """
        assigned_schedule = []

        for shift in empty_schedule:
            shift_key = (shift.date.day, shift.shift_type, shift.pod)
            assigned_residents = []
            
            # We can iterate directly since we know all keys exist
            for r_idx, resident in enumerate(self.residents):
                if solver.Value(shift_vars[r_idx][shift_key]) == 1:
                    assigned_residents.append(resident)

            if assigned_residents:
                new_shift = Shift(
                    date=shift.date,
                    shift_type=shift.shift_type,
                    pod=shift.pod
                )
                for resident in assigned_residents:
                    new_shift.add_resident(resident)
                assigned_schedule.append(new_shift)
                logging.info(f"✅ {shift.date} - {shift.shift_type} - {shift.pod} assigned to {', '.join(r.name for r in assigned_residents)}")
            else:
                logging.warning(f"⚠️ Unstaffed shift: {shift.date}, {shift.shift_type}, {shift.pod}")
        
        # Add this near the end of _convert_solution_to_schedule before returning the schedule:

        # Validate day/night transitions
        for resident in self.residents:
            resident_shifts = sorted([s for s in assigned_schedule if resident in s.residents], 
                                key=lambda x: x.date)
            for i in range(len(resident_shifts)-1):
                current = resident_shifts[i]
                next_shift = resident_shifts[i+1]
                if current.shift_type != next_shift.shift_type:
                    hours_between = (next_shift.date - current.date).total_seconds() / 3600
                    logging.info(f"Resident {resident.name}: {hours_between}h between "
                                f"{current.shift_type.value} and {next_shift.shift_type.value} shifts")


        return assigned_schedule


    def generate_schedule(self) -> List[Shift]:
        """
        Main scheduling algorithm using constraint satisfaction.
        Returns a list of shifts with assigned residents.
        """
        empty_schedule = self._initialize_empty_schedule()
        
        # Use Google OR-Tools for constraint satisfaction
        model, solver, shift_vars = self._setup_solver()
        status = solver.Solve(model)

        logging.info(f"Solver status: {status}")

        if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
            logging.error("❌ No feasible solution found! Debugging constraint issues...")
            
            # Log required shifts per resident
            for resident in self.residents:
                required_shifts = resident.get_required_shifts(
                    self.block.start_date.month,
                    self.block.start_date.year
                )
                logging.debug(f"Resident {resident.name} requires {required_shifts} shifts")

            return []  # Prevent crash, return empty schedule

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            # Generate the schedule
            schedule = self._convert_solution_to_schedule(solver, shift_vars, empty_schedule)

            # Calculate staffed vs. unstaffed shifts
            num_staffed = sum(1 for shift in schedule if shift.residents)
            num_unstaffed = sum(1 for shift in schedule if not shift.residents)

            # Log shift statistics
            logging.info(f"✅ Staffed Shifts: {num_staffed}")
            logging.info(f"⚠️ Unstaffed Shifts: {num_unstaffed}")

            # Count shifts per resident
            resident_shift_counts = {resident.name: 0 for resident in self.residents}
            for shift in schedule:
                for resident in shift.residents:  # Changed from shift.resident
                    resident_shift_counts[resident.name] += 1

            logging.info("📊 Resident Shift Analysis:")
            for resident in self.residents:
                required_shifts = resident.get_required_shifts(self.month, self.year)
                assigned_shifts = resident_shift_counts.get(resident.name, 0)
                logging.info(f"🧑‍⚕️ {resident.name}: Required {required_shifts}, Assigned {assigned_shifts}")

            return schedule
    
        raise ValueError("No valid schedule found satisfying all constraints")
    
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