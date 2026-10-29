"""
Unit Tests for Voter Card Parser & EPIC Normalization Engine.
Complies with ISO/IEC/IEEE 29119-3:2013 (SDLC Phase 4).
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.electoral_engine.parser import VoterCardParser

class TestVoterCardParserEPIC(unittest.TestCase):
    def setUp(self):
        self.parser = VoterCardParser()

    def test_epic_exact_format(self):
        self.assertEqual(self.parser.normalize_epic_candidate("YOU1234567"), "YOU1234567")
        self.assertEqual(self.parser.normalize_epic_candidate("WUZ1234567"), "WUZ1234567")
        self.assertEqual(self.parser.normalize_epic_candidate("IMZ1234567"), "IMZ1234567")

    def test_epic_lookalike_digit_substitution(self):
        # O -> 0, I -> 1, Z -> 2, S -> 5, B -> 8
        self.assertEqual(self.parser.normalize_epic_candidate("YOU123O567"), "YOU1230567")
        self.assertEqual(self.parser.normalize_epic_candidate("YOU123I567"), "YOU1231567")
        self.assertEqual(self.parser.normalize_epic_candidate("YOU123Z567"), "YOU1232567")
        self.assertEqual(self.parser.normalize_epic_candidate("YOU123S567"), "YOU1235567")
        self.assertEqual(self.parser.normalize_epic_candidate("YOU123B567"), "YOU1238567")

    def test_epic_prefix_kerning_fusions(self):
        # YOUM + 5 digits -> YOU14 + 5 digits
        self.assertEqual(self.parser.normalize_epic_candidate("YOUM12345"), "YOU1412345")
        # WUZM + 5 digits -> WUZ14 + 5 digits
        self.assertEqual(self.parser.normalize_epic_candidate("WUZM12345"), "WUZ1412345")
        # IMZN + 6 digits -> IMZ1 + 6 digits
        self.assertEqual(self.parser.normalize_epic_candidate("IMZN123456"), "IMZ1123456")

    def test_door_cleaning(self):
        self.assertEqual(self.parser.clean_door("D.No: 3-109"), "3-109")
        self.assertEqual(self.parser.clean_door("H.No. 4/40B"), "4/40B")
        self.assertEqual(self.parser.clean_door("House Number: 1-8 Photo Available"), "1-8")

if __name__ == "__main__":
    unittest.main()
