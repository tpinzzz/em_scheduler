from src.models import Resident, TimeOff, ResidentLevel, Pod, Shift, Rotation, RotationType, Block
from src.scheduler import Scheduler
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

def main():
    residents = load_residents()
    
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
        save_schedule(schedule, f"schedule_{block.start_date.strftime('%Y_%m')}.json")
        logging.info("Schedule generated successfully!")
    except ValueError as e:
        logging.error(f"Error generating schedule: {e}")

if __name__ == "__main__":
    main()