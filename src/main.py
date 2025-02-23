from models import Resident, TimeOff, ResidentLevel, Pod, Shift, Rotation, RotationType, Block
from scheduler import Scheduler
import json
from datetime import datetime
from typing import List
import logging

# Set up logging at the module level, before any functions
log_filename = f"scheduler_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_residents() -> List[Resident]:
    try:
        with open('data/residents.json', 'r') as f:
            data = json.load(f)
        
        residents = []
        for r in data['residents']:
            # Convert time_off strings to datetime objects
            time_off_list = []
            for to in r['time_off']:
                time_off_list.append(
                    TimeOff(
                        start_date= datetime.strptime(to['start_date'],'%Y-%m-%d'),
                        end_date= datetime.strptime(to['end_date'],'%Y-%m-%d'),
                        is_pto=to['is_pto']
                    )
                )
            
            # Create resident object
            resident = Resident(
                id=r['id'],
                name=r['name'],
                level=ResidentLevel[r['level']],
                pod_preferences=[Pod[p] for p in r['pod_preferences']],
                time_off=time_off_list
            )
            
            # Add dummy ER rotations for blocks 1-13
            logging.debug(f"Adding dummy ER rotations for resident {resident.name}")
            for block_num in range(1, 14):
                resident.rotations[block_num] = Rotation(
                    block_number=block_num,
                    rotation_type=RotationType.ER,
                    is_flexible=True
                )
            
            residents.append(resident)
        
        logging.info(f"Successfully loaded {len(residents)} residents")
        return residents
    except FileNotFoundError:
        logging.error("residents.json not found. Using empty resident list.")
        return []

def save_schedule(schedule: List[Shift], filename: str):
    """Save generated schedule to JSON file."""
    schedule_dict = {
        "month": schedule[0].date.month,
        "year": schedule[0].date.year,
        "shifts": [
            {
                "date": shift.date.isoformat(),
                "type": shift.shift_type.value,
                "pod": shift.pod.value,
                "residents": [resident.name for resident in shift.residents] if shift.residents else []
            }
            for shift in schedule
        ]
    }
    
    with open(filename, 'w') as f:
        json.dump(schedule_dict, f, indent=2)
    logging.info(f"Schedule saved to {filename}")

# In main.py, modify the shift analysis section:

#logging setup below
def setup_logging():
    # Clear any existing handlers
    logging.getLogger().handlers = []
    
    # Create a new log filename with timestamp
    log_filename = f"main_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configure logging to only capture logs from main
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        force=True
    )
    
    # Set other loggers to WARNING level
    for logger_name in logging.root.manager.loggerDict:
        if logger_name != "__main__":
            logging.getLogger(logger_name).setLevel(logging.WARNING)

def main():
    setup_logging() 
    residents = load_residents()
    logging.info(f"Loaded {len(residents)} residents")
    
    # Create Block 1 for current academic year
    current_year = datetime.now().year
    academic_year = current_year if datetime.now().month >= 7 else current_year - 1
    block = Block.get_block_dates(1, academic_year)
    
    logging.info(f"Generating schedule for Block 1: {block.start_date.date()} to {block.end_date.date()}")
    
    # Initialize scheduler with block
    scheduler = Scheduler(residents=residents, block=block)
    
    try:
        schedule = scheduler.generate_schedule()
        if not schedule:
            logging.error("No schedule generated")
            return

        logging.info("\nSchedule Analysis - Critical Metrics:")
        
        # 1. Check day/night transitions
        logging.info("\nChecking Day/Night Transitions:")
        for resident in residents:
            resident_shifts = sorted([s for s in schedule if resident in s.residents], 
                                  key=lambda x: x.date)
            for i in range(len(resident_shifts)-1):
                current = resident_shifts[i]
                next_shift = resident_shifts[i+1]
                if current.shift_type != next_shift.shift_type:
                    hours_between = (next_shift.date - current.date).total_seconds() / 3600
                    if hours_between < 48:
                        logging.warning(f"❌ {resident.name}: Only {hours_between}h between "
                                     f"{current.shift_type.value} and {next_shift.shift_type.value}")

        '''# 2. Check PGY1 supervision
        logging.info("\nChecking PGY1 Supervision:")
        pgy1s = [r for r in residents if r.level == ResidentLevel.PGY1]
        for shift in schedule:
            shift_residents = shift.residents
            has_pgy1 = any(r.level == ResidentLevel.PGY1 for r in shift_residents)
            has_supervisor = any(r.level in [ResidentLevel.PGY2, ResidentLevel.PGY3, ResidentLevel.CHIEF] 
                               for r in shift_residents)
            if has_pgy1 and not has_supervisor:
                logging.warning(f"❌ Unsupervised PGY1 on {shift.date.date()} "
                              f"{shift.shift_type.value} {shift.pod.value}")

        # 3. Check consecutive shifts
        logging.info("\nChecking Consecutive Shifts:")
        for resident in residents:
            resident_shifts = sorted([s for s in schedule if resident in s.residents], 
                                  key=lambda x: x.date)
            consecutive_count = 1
            for i in range(1, len(resident_shifts)):
                if (resident_shifts[i].date - resident_shifts[i-1].date).days == 1:
                    consecutive_count += 1
                    if consecutive_count > 6:
                        logging.warning(f"❌ {resident.name} has {consecutive_count} "
                                     f"consecutive shifts starting {resident_shifts[i-6].date.date()}")
                else:
                    consecutive_count = 1

        # 4. Shift distribution summary
        shift_stats = {}
        for shift in schedule:
            key = (shift.shift_type.value, shift.pod.value)
            if key not in shift_stats:
                shift_stats[key] = {"count": 0, "total_residents": 0}
            shift_stats[key]["count"] += 1
            shift_stats[key]["total_residents"] += len(shift.residents)

        logging.info("\nShift Distribution Summary:")
        for (shift_type, pod), stats in shift_stats.items():
            avg_residents = stats["total_residents"] / stats["count"] if stats["count"] > 0 else 0
            logging.info(f"{shift_type.upper()} - {pod.upper()}: {stats['count']} shifts, "
                        f"{stats['total_residents']} total assignments "
                        f"(avg {avg_residents:.1f} residents/shift)")

        # 5. Check resident assignments
        logging.info("\nResident Assignment Summary:")
        for resident in residents:
            assigned_shifts = len([s for s in schedule if resident in s.residents])
            required_shifts = resident.get_required_shifts(
                block.start_date.month,
                block.start_date.year
            )
            logging.info(f"{resident.name} ({resident.level.value}): "
                        f"Required {required_shifts}, Assigned {assigned_shifts}")
        '''
        # Save schedule
        save_schedule(schedule, f"schedule_{block.start_date.strftime('%Y_%m')}.json")
        logging.info("\nSchedule generated and saved successfully!")
        
    except ValueError as e:
        logging.error(f"Error generating schedule: {e}")

if __name__ == "__main__":
    main()