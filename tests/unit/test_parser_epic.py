"""
Unit Tests for Voter Card Parser & EPIC Normalization Engine.
"""
import pytest
from src.electoral_engine.parser import VoterCardParser

def test_epic_exact_format():
    parser = VoterCardParser()
    assert parser.normalize_epic_candidate("YOU1234567") == "YOU1234567"
    assert parser.normalize_epic_candidate("WUZ1234567") == "WUZ1234567"
    assert parser.normalize_epic_candidate("IMZ1234567") == "IMZ1234567"

def test_epic_lookalike_digit_substitution():
    parser = VoterCardParser()
    # O -> 0, I -> 1, Z -> 2, S -> 5, B -> 8
    assert parser.normalize_epic_candidate("YOU123O567") == "YOU1230567"
    assert parser.normalize_epic_candidate("YOU123I567") == "YOU1231567"
    assert parser.normalize_epic_candidate("YOU123Z567") == "YOU1232567"
    assert parser.normalize_epic_candidate("YOU123S567") == "YOU1235567"
    assert parser.normalize_epic_candidate("YOU123B567") == "YOU1238567"

def test_epic_prefix_kerning_fusions():
    parser = VoterCardParser()
    # YOUM + 5 digits -> YOU14 + 5 digits
    assert parser.normalize_epic_candidate("YOUM12345") == "YOU1412345"
    # WUZM + 5 digits -> WUZ14 + 5 digits
    assert parser.normalize_epic_candidate("WUZM12345") == "WUZ1412345"
    # IMZN + 6 digits -> IMZ1 + 6 digits
    assert parser.normalize_epic_candidate("IMZN123456") == "IMZ1123456"

def test_door_cleaning():
    parser = VoterCardParser()
    assert parser.clean_door("D.No: 3-109") == "3-109"
    assert parser.clean_door("H.No. 4/40B") == "4/40B"
    assert parser.clean_door("House Number: 1-8 Photo Available") == "1-8"
