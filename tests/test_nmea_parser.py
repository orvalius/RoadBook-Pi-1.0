"""Tests de core.nmea_parser."""

from __future__ import annotations

from core.nmea_parser import parse_gga, parse_rmc, verify_checksum


def test_verify_checksum_valid() -> None:
    # Sentencia real con checksum correcto
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    assert verify_checksum(sentence) is True


def test_verify_checksum_invalid() -> None:
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*00"
    assert verify_checksum(sentence) is False


def test_verify_checksum_missing_asterisk() -> None:
    assert verify_checksum("$GPGGA,123519,4807.038,N") is False


def test_parse_gga_with_fix() -> None:
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    result = parse_gga(sentence)
    assert result is not None
    assert result["has_fix"] is True
    assert round(result["latitude"], 3) == round(48 + 7.038 / 60, 3)
    assert round(result["longitude"], 3) == round(11 + 31.000 / 60, 3)


def test_parse_gga_without_fix() -> None:
    sentence = "$GPGGA,123519,,,,,0,00,,,M,,M,,*66"
    result = parse_gga(sentence)
    assert result is not None
    assert result["has_fix"] is False


def test_parse_gga_wrong_sentence_type_returns_none() -> None:
    assert parse_gga("$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A") is None


def test_parse_rmc_active_status() -> None:
    sentence = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
    result = parse_rmc(sentence)
    assert result is not None
    assert result["has_fix"] is True
    assert result["heading"] == 84.4
    assert round(result["speed"], 1) == round(22.4 * 1.852, 1)


def test_parse_rmc_void_status() -> None:
    sentence = "$GPRMC,123519,V,,,,,,,230394,,,N*53"
    result = parse_rmc(sentence)
    assert result is not None
    assert result["has_fix"] is False


def test_parse_rmc_wrong_sentence_type_returns_none() -> None:
    assert parse_rmc("$GPGGA,123519,,,,,0,00,,,M,,M,,*66") is None
