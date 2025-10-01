import pytest
from pathlib import Path
from src.decoders.asterix_file_reader import AsterixFileReader

@pytest.mark.parametrize(
    "file,number",
    [
        ("datos_asterix_adsb.ast", 975101),  # replace 10 with the expected record count
        ("datos_asterix_radar.ast", 503698),     # add more test files as needed
        ("datos_asterix_combinado.ast", 1478799)
    ]
)
def test_file_reader_records_number(file: str, number: int):
    """Test that the file contains the expected number of ASTERIX records."""

    # Navigate to the project root
    base_dir = Path(__file__).resolve().parent.parent
    file_path = base_dir / "data" / "samples" / file

    reader = AsterixFileReader(str(file_path))

    # Convert generator to list to count records
    records = list(reader.read_records())

    assert len(records) == number, f"Expected {number} records, got {len(records)}"
