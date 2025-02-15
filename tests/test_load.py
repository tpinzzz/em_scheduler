# tests/test_load.py
from src.main import load_residents

def test_load_residents():
    try:
        residents = load_residents()
        print(f"Successfully loaded {len(residents)} residents:")
        for resident in residents:
            print(f"- {resident.name} ({resident.level.value})")
        return True
    except Exception as e:
        print(f"Error loading residents: {e}")
        return False

if __name__ == "__main__":
    test_load_residents()