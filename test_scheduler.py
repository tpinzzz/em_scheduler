# test_scheduler.py

import json
import logging
from datetime import datetime
from src.models import Resident, ResidentLevel, Pod, TimeOff, Block, Rotation, RotationType
from src.scheduler import Scheduler

def setup_logging():
    """Configure logging for testing"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("test_scheduler.log")
        ]
    )

def load_test_residents():
    """Load residents from the data file"""
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
                        start_date=datetime.strptime(to['start_date'],'%Y-%m-%d'),
                        end_date=datetime.strptime(to['end_date'],'%Y-%m-%d'),
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
            
            # Add dummy ER rotations for block 1
            for block_num in range(1, 14):
                resident.rotations[block_num] = Rotation(
                    block_number=block_num,
                    rotation_type=RotationType.ER,
                    is_flexible=True
                )
            
            residents.append(resident)
        
        logging.info(f"Loaded {len(residents)} residents for testing")
        return residents
    except FileNotFoundError:
        logging.error("residents.json not found")
        return []

def save_schedule_for_chief(schedule, filename=None):
    """Save the schedule in a user-friendly format for the chief"""
    if filename is None:
        filename = f"schedule_block1_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    
    schedule_data = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_shifts": len(schedule),
            "staffed_shifts": sum(1 for s in schedule if s.residents)
        },
        "shifts": []
    }
    
    for shift in schedule:
        shift_data = {
            "date": shift.date.strftime("%Y-%m-%d"),
            "day_of_week": shift.date.strftime("%A"),
            "shift_type": shift.shift_type.value,
            "pod": shift.pod.value,
            "residents": [
                {"name": r.name, "level": r.level.value} for r in shift.residents
            ]
        }
        schedule_data["shifts"].append(shift_data)
    
    with open(filename, 'w') as f:
        json.dump(schedule_data, f, indent=2)
    
    print(f"Schedule saved to {filename}")
    return filename


def test_schedule_generation():
    """Test scheduler with July data"""
    setup_logging()
    residents = load_test_residents()
    
    # Create Block 1 for July 2024
    block = Block.get_block_dates(1, 2024)
    logging.info(f"Generating schedule for Block 1: {block.start_date.date()} to {block.end_date.date()}")
    
    # Initialize scheduler with block
    scheduler = Scheduler(residents=residents, block=block)
    
    # Generate schedule
    logging.info("Generating schedule...")
    schedule = scheduler.generate_schedule()
    
    if not schedule:
        logging.error("Failed to generate schedule")
        return
    
    logging.info(f"Successfully generated schedule with {len(schedule)} shifts")
    
    # Print some basic statistics about the schedule
    staffed_shifts = sum(1 for s in schedule if s.residents)
    logging.info(f"Staffed shifts: {staffed_shifts}")
    
    # Count shifts by type and pod
    shift_counts = {
        "day_purple": 0,
        "day_orange": 0,
        "night_purple": 0,
        "night_orange": 0,
        "swing_purple": 0,
        "swing_orange": 0
    }
    
    for shift in schedule:
        key = f"{shift.shift_type.value}_{shift.pod.value}"
        if key in shift_counts:
            shift_counts[key] += 1
    
    logging.info("\nShift distribution:")
    for shift_type, count in shift_counts.items():
        logging.info(f"{shift_type}: {count}")

    save_schedule_for_chief(schedule)
    
    return schedule

if __name__ == "__main__":
    schedule = test_schedule_generation()
    print(f"Test completed. See test_scheduler.log for details.")