import pytest
from datetime import datetime, timedelta
from src.models import Block, RotationType, Rotation, Resident, ResidentLevel, Pod

class TestBlock:
    def test_block_dates_calculation(self):
        """Test automatic block date calculations"""
        # Block 1 (July)
        block1 = Block.get_block_dates(1, 2024)
        assert block1.number == 1
        assert block1.start_date == datetime(2024, 7, 1)
        assert block1.end_date == datetime(2024, 7, 28)
        
        # Block 7 (January) - crosses calendar year
        block7 = Block.get_block_dates(7, 2024)
        assert block7.number == 7
        assert block7.start_date.year == 2024
        assert block7.start_date.month == 12
        
        # Block 13 (June) - special case
        block13 = Block.get_block_dates(13, 2024)
        assert block13.start_date == datetime(2025, 6, 2)
        assert block13.end_date == datetime(2025, 6, 30)

    def test_block_transitions(self):
        """Test that blocks transition correctly"""
        blocks = [Block.get_block_dates(i, 2024) for i in range(1, 14)]
        
        # Check consecutive blocks
        for i in range(len(blocks)-1):
            current = blocks[i]
            next_block = blocks[i+1]
            assert (next_block.start_date - current.end_date).days == 1

    def test_block_validation(self):
        """Test block validation rules"""
        with pytest.raises(ValueError):
            Block.get_block_dates(0, 2024)  # Invalid block number
        
        with pytest.raises(ValueError):
            Block.get_block_dates(14, 2024)  # Invalid block number

    @pytest.fixture
    def test_resident(self):
        resident = Resident(
            id="TEST001",
            name="Test Resident",
            level=ResidentLevel.PGY2,
            pod_preferences=[Pod.PURPLE, Pod.ORANGE],
            time_off=[]
        )
        resident.rotations= {
                1: Rotation(1, RotationType.ER, True),
                2: Rotation(2, RotationType.ICU, False)
        }
        return resident

    def test_block_transition_days(self, test_resident: Resident):
        """Test resident availability on block transition days"""
        # Set up ER to ER transition
        test_resident.rotations = {
            1: Rotation(1, RotationType.ER, True),
            2: Rotation(2, RotationType.ER, True)
        }
        block1 = Block.get_block_dates(1, 2024)
        assert test_resident.can_work_transition_day(block1.end_date, False)

    def test_academic_year_transition(self):
        """Test blocks across academic year transition"""
        # Block 13 2024 to Block 1 2025
        block13_2024 = Block.get_block_dates(13, 2024)
        block1_2025 = Block.get_block_dates(1, 2025)
        
        assert block13_2024.end_date.month == 6
        assert block13_2024.end_date.year == 2025
        assert block1_2025.start_date.month == 7
        assert block1_2025.start_date.year == 2025
        assert (block1_2025.start_date - block13_2024.end_date).days == 1