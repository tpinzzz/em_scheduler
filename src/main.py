from models import *
from scheduler import Scheduler
import json
from datetime import datetime

def load_residents() -> List[Resident]:
    """Load resident data from configuration file."""
    # Implementation to load resident data
    pass

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
                "resident": shift.resident.name if shift.resident else None
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
        save_schedule(schedule, f"schedule_{datetime.now().strftime('%Y_%m')}.json")
        print("Schedule generated successfully!")
    except ValueError as e:
        print(f"Error generating schedule: {e}")

if __name__ == "__main__":
    main()