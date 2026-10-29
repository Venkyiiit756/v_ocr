"""
Multi-Scale Proximity Surname Restoration Verification Suite (DEIP V2.2)
Verifies:
1. Tier 1: Intra-Card Mutual Surname Restoration & Pasham Cultural Safeguard
2. Tier 2: Household Door-Consensus Bayesian Prior Arbitration
3. Tier 3: Serial Adjacency Sliding Window (Street-Level Neighbors)
4. Dual-CASL Immunity Barrier (Distinct authentic surnames are NEVER merged)
5. Absolute Vowel Immunity (Complete vowel-terminated surnames never elongated)
"""

import os
import sys
import unittest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.electoral_engine.reconciler import ElectoralReconciler, can_safely_repair_surname


class TestMultiScaleProximity(unittest.TestCase):

    def setUp(self):
        self.reconciler = ElectoralReconciler()

    def test_can_safely_repair_surname_safeguards(self):
        """Verify Dual-CASL, Vowel, and Halanta immunity barriers."""
        # Terminal smudge repair
        self.assertTrue(can_safely_repair_surname("Chagantl", "Chaganti"))
        self.assertTrue(can_safely_repair_surname("Palepl", "Palepu"))
        self.assertTrue(can_safely_repair_surname("Boddl", "Boddu"))

        # Broken halanta / cutoff repair
        self.assertTrue(can_safely_repair_surname("Salad", "Saladi"))
        self.assertTrue(can_safely_repair_surname("Palik", "Paliki"))

        # Dual-CASL Immunity: Both are authentic distinct Andhra surnames
        self.assertFalse(can_safely_repair_surname("Boppana", "Boppanna"))
        self.assertFalse(can_safely_repair_surname("Palika", "Paliki"))
        self.assertFalse(can_safely_repair_surname("Kona", "Konda"))

        # Protected Halanta Blocklist
        self.assertFalse(can_safely_repair_surname("Shaik", "Shaiku"))
        self.assertFalse(can_safely_repair_surname("David", "Davidu"))
        self.assertFalse(can_safely_repair_surname("Kiran", "Kiranu"))

        # Absolute Vowel Immunity (already complete)
        self.assertFalse(can_safely_repair_surname("Ganta", "Gantaa"))
        self.assertFalse(can_safely_repair_surname("Nakka", "Nakkaa"))

    def test_tier_1_intra_card_repair(self):
        """Verify intra-card mutual surname repair between voter and relative."""
        records = [
            {
                'elector_id': '37_1_1',
                'voter_name_en': 'Chagantl Apparao',
                'rel_name_en': 'Chaganti Subbarao',
                'door_no': '1-10',
                'audit_trail': []
            },
            {
                'elector_id': '37_1_2',
                'voter_name_en': 'Pasha Venkata Ramana',
                'rel_name_en': 'Pasham Subbarao',
                'door_no': '1-12',
                'audit_trail': []
            }
        ]

        repaired = self.reconciler.repair_intra_card(records)

        # Record 1: Chagantl -> Chaganti
        self.assertEqual(repaired[0]['voter_name_en'], 'Chaganti Apparao')
        self.assertTrue(any(a['tier'] == 'TIER_1_INTRA_CARD' for a in repaired[0]['audit_trail']))

        # Record 2: Pasha -> Pasham
        self.assertEqual(repaired[1]['voter_name_en'], 'Pasham Venkata Ramana')
        self.assertTrue(any('Pasham Cultural Safeguard' in a['rationale'] for a in repaired[1]['audit_trail']))

    def test_tier_2_household_door_consensus(self):
        """Verify household consensus repairs smudged co-resident surname."""
        records = [
            {
                'elector_id': '37_1_10',
                'assembly_part_no': 1,
                'normalized_door_no': '4-40B',
                'door_no': '4-40B',
                'voter_name_en': 'Medisetti Apparao',
                'rel_name_en': 'Medisetti Suryanarayana',
                'audit_trail': []
            },
            {
                'elector_id': '37_1_11',
                'assembly_part_no': 1,
                'normalized_door_no': '4-40B',
                'door_no': '4-40B',
                'voter_name_en': 'Medisett Durga',
                'rel_name_en': 'Medisetti Apparao',
                'audit_trail': []
            }
        ]

        repaired = self.reconciler.repair_household_door_consensus(records)
        self.assertEqual(repaired[1]['voter_name_en'], 'Medisetti Durga')
        self.assertTrue(any(a['tier'] == 'TIER_2_HOUSEHOLD' for a in repaired[1]['audit_trail']))

    def test_tier_3_serial_street_adjacency(self):
        """Verify serial street adjacency repairs neighbor along same street."""
        records = [
            {
                'elector_id': '37_1_100',
                'assembly_part_no': 1,
                'booth_sno': 100,
                'voter_name_en': 'Koppisetti Subbarao',
                'rel_name_en': 'Koppisetti Appanna',
                'audit_trail': []
            },
            {
                'elector_id': '37_1_101',
                'assembly_part_no': 1,
                'booth_sno': 101,
                'voter_name_en': 'Koppisett Ramana',
                'rel_name_en': 'Koppisett Tatabbai',
                'audit_trail': []
            }
        ]

        repaired = self.reconciler.repair_serial_adjacency(records)
        self.assertEqual(repaired[1]['voter_name_en'], 'Koppisetti Ramana')
        self.assertTrue(any(a['tier'] == 'TIER_3_SERIAL_STREET' for a in repaired[1]['audit_trail']))


if __name__ == '__main__':
    unittest.main()
