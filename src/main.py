from src.models import Resident, TimeOff, ResidentLevel, Pod, Shift, Rotation, RotationType
from src.scheduler import Scheduler
import json
from datetime import datetime
from typing import List

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
                        start_date=datetime.fromisoformat(to['start_date']),
                        end_date=datetime.fromisoformat(to['end_date']),
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
            for block_num in range(1, 14):
                resident.rotations[block_num] = Rotation(
                    block_number=block_num,
                    rotation_type=RotationType.ER,
                    is_flexible=True
                )
            
            residents.append(resident)
        
        return residents
    except FileNotFoundError:
        print("Warning: residents.json not found. Using empty resident list.")
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

def main():
    residents = load_residents()
    scheduler = Scheduler(residents, datetime.now().month, datetime.now().year)
    
    try:
        schedule = scheduler.generate_schedule()
        #DEBUGGING
        if not schedule:
            print("❌ No schedule generated. Exiting early.")
            return
        ##DEBUG STATEMENT END
        save_schedule(schedule, f"schedule_{datetime.now().strftime('%Y_%m')}.json")
        print("Schedule generated successfully!")
    except ValueError as e:
        print(f"Error generating schedule: {e}")

if __name__ == "__main__":
    main()