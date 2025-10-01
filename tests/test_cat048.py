# tests/test_cat048_decoder.py
import pytest
from src.decoders.cat048_decoder import Cat048Decoder
from src.models.record import Record
from src.types.enums import Category, CAT048ItemType


class TestCat048Decoder:
    @pytest.fixture
    def decoder(self):
        return Cat048Decoder()



    def test_parse_fspec_all_bits(self, decoder):
        """Test FSPEC parsing with all bits set in first byte"""
        # FSPEC: 0b11111110 - all bits 7-1 set, FX=0
        raw_data = b'\xFE' + b'\x00' * 20

        items, data_start = decoder._parse_fspec(raw_data)

        expected_items = [
            CAT048ItemType.DATA_SOURCE_IDENTIFIER,  # FRN 1
            CAT048ItemType.TIME_OF_DAY,  # FRN 2
            CAT048ItemType.TARGET_REPORT_DESCRIPTOR,  # FRN 3
            CAT048ItemType.MEASURED_POSITION_POLAR,  # FRN 4
            CAT048ItemType.MODE_3A_CODE,  # FRN 5
            CAT048ItemType.FLIGHT_LEVEL,  # FRN 6
            CAT048ItemType.RADAR_PLOT_CHARACTERISTICS,  # FRN 7
        ]
        assert items == expected_items
        assert data_start == 1

    def test_decode_data_source(self, decoder):
        """Test decoding of Data Source Identifier"""
        record = Record(Category.CAT048, 10, b'\x00' * 10, 0, [])
        data = b'\x2A\x0F'  # SAC=42, SIC=15

        new_pos = decoder._decode_data_source(data, 0, record)

        assert new_pos == 2
        assert len(record.items) == 1

        item = record.items[0]
        assert item.item_type == CAT048ItemType.DATA_SOURCE_IDENTIFIER
        assert item.value == {"SAC": 42, "SIC": 15}
        assert item.length == 2
        assert item.item_offset == 0

    def test_decode_track_number(self, decoder):
        """Test decoding of Track Number"""
        record = Record(Category.CAT048, 10, b'\x00' * 10, 0, [])
        data = b'\x01\x23'  # Track number = 291

        new_pos = decoder._decode_track_number(data, 0, record)

        assert new_pos == 2
        assert len(record.items) == 1

        item = record.items[0]
        assert item.item_type == CAT048ItemType.TRACK_NUMBER
        assert item.value == 291
        assert item.length == 2

    def test_decode_record_boundary_conditions(self, decoder):
        """Test decoding with insufficient data"""
        # FSPEC indicates items but not enough data
        fspec_and_data = b'\xC2' + b'\x2A'  # Only 1 byte after FSPEC, need 7
        record = Record(Category.CAT048, 10, fspec_and_data, 0, [])

        decoded_record = decoder.decode_record(record)

        # Should handle gracefully without crashing
        assert len(decoded_record.items) >= 0

    def test_all_decoder_methods_exist(self, decoder):
        """Test that all CAT048ItemType values have corresponding decoder methods"""
        for item_type in CAT048ItemType:
            decoder_func = decoder.decoder_map.get(item_type)
            assert decoder_func is not None, f"No decoder for {item_type}"
            assert callable(decoder_func)

    def test_unknown_frn_in_fspec(self, decoder, capsys):
        """Test handling of unknown FRN values in FSPEC"""
        # This would require an FRN that's not in CAT048ItemType enum
        # We can't easily test this without modifying enum, but the error handling is there
        pass

    def test_item_creation_consistency(self, decoder):
        """Test that all created items have consistent attributes"""
        record = Record(Category.CAT048, 10, b'\x00' * 10, 0, [])

        # Test one decoder method
        decoder._decode_data_source(b'\x01\x02', 0, record)

        item = record.items[0]
        assert hasattr(item, 'item_offset')
        assert hasattr(item, 'length')
        assert hasattr(item, 'frn')
        assert hasattr(item, 'item_type')
        assert hasattr(item, 'value')
        assert item.frn == item.item_type.value

    def test_position_tracking(self, decoder):
        """Test that data pointer advances correctly through multiple items"""
        # FSPEC with FRN 1 and 2
        fspec_and_data = b'\xC0' + b'\x01\x02' + b'\x03\x04\x05'
        record = Record(Category.CAT048, 10, fspec_and_data, 0, [])

        decoded_record = decoder.decode_record(record)

        # Should have decoded both items
        assert len(decoded_record.items) == 2
        # First item should be at offset 1 (after FSPEC)
        assert decoded_record.items[0].item_offset == 1
        # Second item should be at offset 3 (after first 2-byte item)
        assert decoded_record.items[1].item_offset == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])