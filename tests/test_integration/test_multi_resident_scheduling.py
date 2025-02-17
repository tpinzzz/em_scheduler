from datetime import datetime
from src.main import load_residents
from src.models import Block
from src.scheduler import Scheduler

def test_multi_resident_scheduling():
    # Load residents
    residents = load_residents()
    print(f"\nLoaded {len(residents)} residents")
    
    # Create a test block (using Block 1 as example)
    block = Block(
        number=1,
        start_date=datetime(2024, 7, 1),
        end_date=datetime(2024, 7, 28)
    )
    
    # Initialize scheduler
    scheduler = Scheduler(residents=residents, block=block)
    
    # Generate schedule
    print("\nGenerating schedule...")
    schedule = scheduler.generate_schedule()
    
    if not schedule:
        print("❌ Failed to generate schedule")
        return
    
    # Analyze the results
    print("\nAnalyzing schedule:")
    shift_stats = {}  # (pod, shift_type) -> count of residents
    
    for shift in schedule:
        key = (shift.pod.value, shift.shift_type.value)
        resident_count = len(shift.residents)
        
        if key not in shift_stats:
            shift_stats[key] = []
        shift_stats[key].append(resident_count)
    
    # Print statistics
    print("\nShift Staffing Summary:")
    for (pod, shift_type), counts in shift_stats.items():
        avg_residents = sum(counts) / len(counts)
        max_residents = max(counts)
        print(f"\n{pod.upper()} {shift_type.upper()}:")
        print(f"- Average residents per shift: {avg_residents:.1f}")
        print(f"- Maximum residents on any shift: {max_residents}")
        print(f"- Total shifts of this type: {len(counts)}")

if __name__ == "__main__":
    test_multi_resident_scheduling()