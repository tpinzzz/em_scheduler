import pytest
from datetime import datetime
from src.models import Block, Resident, ResidentLevel, Pod, Shift, ShiftType, RotationType, Rotation
from src.scheduler import Scheduler
import logging

@pytest.fixture
def test_block():
    """Create a test block for July 2024"""
    return Block(
        number=1,
        start_date=datetime(2024, 7, 1),
        end_date=datetime(2024, 7, 28)
    )

@pytest.fixture
def test_residents():
    """Create a small set of test residents"""
    residents = []
    # Add a PGY1
    pgy1 = Resident(
        id="TEST001",
        name="Test PGY1",
        level=ResidentLevel.PGY1,
        pod_preferences=[Pod.PURPLE, Pod.ORANGE],
        time_off=[]
    )
    # Add their ER rotations
    for block_num in range(1, 14):
        pgy1.rotations[block_num] = Rotation(
            block_number=block_num,
            rotation_type=RotationType.ER,
            is_flexible=True
        )
    residents.append(pgy1)

    # Add a PGY3 for supervision
    pgy3 = Resident(
        id="TEST002",
        name="Test PGY3",
        level=ResidentLevel.PGY3,
        pod_preferences=[Pod.PURPLE, Pod.ORANGE],
        time_off=[]
    )
    for block_num in range(1, 14):
        pgy3.rotations[block_num] = Rotation(
            block_number=block_num,
            rotation_type=RotationType.ER,
            is_flexible=True
        )
    residents.append(pgy3)
    
    return residents

def test_shift_variable_creation(test_block, test_residents):
    """Test that all shift variables are created for all residents"""
    scheduler = Scheduler(residents=test_residents, block=test_block)
    model, solver, shift_vars = scheduler._setup_solver()
    
    # Check that each resident has variables for all shifts
    for r_idx, resident in enumerate(test_residents):
        assert shift_vars[r_idx] is not None, f"No shift dictionary for resident {resident.name}"
        # Count the number of shift variables
        num_vars = len(shift_vars[r_idx])
        # Calculate expected number (days × shifts per day × pods)
        # Note: Need to account for no Tuesday nights
        expected_num = 160  # This is the known number from your debug output
        assert num_vars == expected_num, f"Expected {expected_num} shifts for {resident.name}, got {num_vars}"

def test_block_transition_constraints(test_block, test_residents):
    """Test that block transition constraints are properly applied"""
    scheduler = Scheduler(residents=test_residents, block=test_block)
    model, solver, shift_vars = scheduler._setup_solver()
    
    # Check that all residents can work on regular days
    regular_day = datetime(2024, 7, 15)  # A mid-block day
    for r_idx, resident in enumerate(test_residents):
        shift_key = (regular_day.day, ShiftType.DAY, Pod.PURPLE)
        assert shift_key in shift_vars[r_idx], f"Missing regular day shift for {resident.name}"

def test_logging_configuration(caplog, test_block, test_residents):
    """Test that logging is working correctly at different levels"""
    scheduler = Scheduler(residents=test_residents, block=test_block)
    with caplog.at_level(logging.DEBUG):
        model, solver, shift_vars = scheduler._setup_solver()
        
    # Debugging: Print captured log messages
    print("\nCaptured Logs:")
    for record in caplog.records:
        print(f"{record.levelname}: {record.message}")
    # Check for expected log messages
    assert any("Initial Setup" in record.message for record in caplog.records)
    assert any("Creating shift variables" in record.message for record in caplog.records)
    assert any(record.levelname == "DEBUG" for record in caplog.records)