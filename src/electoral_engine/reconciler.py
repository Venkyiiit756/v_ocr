"""
Master Entity Reconciler & Data Integrity Engine.
Merges ground-truth municipal / ward voter registries with official roll extractions
using deterministic multi-tier matching while preventing hallucination or guesswork.
"""

import re
import difflib

class ElectoralReconciler:
    def __init__(self, ground_truth_records, key_field='EPIC No'):
        self.ground_truth = ground_truth_records
        self.key_field = key_field

    def reconcile(self, extracted_roll_records):
        """
        Reconciles extracted roll records against the ground truth.
        Multi-tier:
          Tier 1: Exact EPIC match
          Tier 2: 1-character OCR error fuzzy EPIC match
          Tier 3: High-confidence name matching on remaining unclaimed cards
        """
        # Index roll records by card id
        for idx, rec in enumerate(extracted_roll_records):
            rec['_cid'] = idx

        # Lookups
        roll_by_epic = {}
        for rec in extracted_roll_records:
            e = rec.get('epic_no', '').strip().upper()
            if e and e not in roll_by_epic:
                roll_by_epic[e] = rec

        matched_cards = set()
        elector_matches = {}

        # ----------------------------------------------------
        # TIER 1: Exact EPIC Match
        # ----------------------------------------------------
        for i, gt in enumerate(self.ground_truth):
            gt_epic = str(gt.get(self.key_field, '')).strip().upper()
            if gt_epic and gt_epic in roll_by_epic:
                card = roll_by_epic[gt_epic]
                if card['_cid'] not in matched_cards:
                    elector_matches[i] = (card, 'Exact EPIC')
                    matched_cards.add(card['_cid'])

        # ----------------------------------------------------
        # TIER 2: Fuzzy EPIC Match (1-character substitution)
        # ----------------------------------------------------
        for i, gt in enumerate(self.ground_truth):
            if i in elector_matches:
                continue
            gt_epic = str(gt.get(self.key_field, '')).strip().upper()
            if not gt_epic or len(gt_epic) != 10:
                continue

            for repic, card in roll_by_epic.items():
                if card['_cid'] in matched_cards:
                    continue
                if repic[:3] == gt_epic[:3] and len(repic) == 10:
                    diffs = sum(1 for a, b in zip(repic[3:], gt_epic[3:]) if a != b)
                    if diffs == 1:
                        elector_matches[i] = (card, 'Fuzzy EPIC (1 char diff)')
                        matched_cards.add(card['_cid'])
                        break

        # ----------------------------------------------------
        # TIER 3: High-Confidence Name Match on Unclaimed Cards
        # Handles Surname-First vs Given-Name-First inverted orders
        # ----------------------------------------------------
        def tokenize_name(name_str):
            clean = re.sub(r'[^a-z\s]', ' ', str(name_str).lower())
            tokens = sorted([t for t in clean.split() if len(t) >= 2])
            return ' '.join(tokens)

        unclaimed_by_tokens = {}
        unclaimed_by_concat = {}
        for card in extracted_roll_records:
            if card['_cid'] in matched_cards:
                continue
            raw_n = card.get('voter_name', '').strip().lower()
            tok_n = tokenize_name(raw_n)
            cn = re.sub(r'[^a-z]', '', raw_n)
            if len(tok_n) >= 4 and tok_n not in unclaimed_by_tokens:
                unclaimed_by_tokens[tok_n] = card
            if len(cn) >= 5 and cn not in unclaimed_by_concat:
                unclaimed_by_concat[cn] = card

        # 3A: Exact Token-Sorted Match (e.g. "Rohila Polukonda" == "POLUKONDA ROHILA")
        for i, gt in enumerate(self.ground_truth):
            if i in elector_matches:
                continue
            raw_gt = str(gt.get('Voter Name (English)', '')).strip().lower()
            tok_gt = tokenize_name(raw_gt)
            if tok_gt and tok_gt in unclaimed_by_tokens:
                card = unclaimed_by_tokens[tok_gt]
                if card['_cid'] not in matched_cards:
                    elector_matches[i] = (card, f'Exact Token Name ({tok_gt})')
                    matched_cards.add(card['_cid'])
                    del unclaimed_by_tokens[tok_gt]

        # 3B: Fuzzy Token / Concatenated Match
        for i, gt in enumerate(self.ground_truth):
            if i in elector_matches:
                continue
            raw_gt = str(gt.get('Voter Name (English)', '')).strip().lower()
            tok_gt = tokenize_name(raw_gt)
            cn_gt = re.sub(r'[^a-z]', '', raw_gt)

            matched_card = None
            match_label = None

            # Check fuzzy on tokenized
            if len(tok_gt) >= 6 and unclaimed_by_tokens:
                tok_matches = difflib.get_close_matches(tok_gt, list(unclaimed_by_tokens.keys()), n=1, cutoff=0.82)
                if tok_matches:
                    best_tok = tok_matches[0]
                    card = unclaimed_by_tokens[best_tok]
                    if card['_cid'] not in matched_cards:
                        matched_card = card
                        match_label = f'Fuzzy Token Name ({best_tok})'
                        del unclaimed_by_tokens[best_tok]

            # Check fuzzy on concat
            if not matched_card and len(cn_gt) >= 6 and unclaimed_by_concat:
                cn_matches = difflib.get_close_matches(cn_gt, list(unclaimed_by_concat.keys()), n=1, cutoff=0.82)
                if cn_matches:
                    best_cn = cn_matches[0]
                    card = unclaimed_by_concat[best_cn]
                    if card['_cid'] not in matched_cards:
                        matched_card = card
                        match_label = f'Fuzzy Name ({best_cn})'
                        del unclaimed_by_concat[best_cn]

            if matched_card:
                elector_matches[i] = (matched_card, match_label)
                matched_cards.add(matched_card['_cid'])

        # ----------------------------------------------------
        # Build Enriched Records & Audit Stats
        # ----------------------------------------------------
        enriched_list = []
        exact_count = 0
        fuzzy_count = 0
        unmatched_count = 0

        for i, gt in enumerate(self.ground_truth):
            enriched_row = dict(gt)
            if i in elector_matches:
                card, match_type = elector_matches[i]
                if match_type == 'Exact EPIC':
                    exact_count += 1
                else:
                    fuzzy_count += 1

                enriched_row['Father / Husband / Guardian Name'] = card.get('rel_name') or '-'
                enriched_row['Relationship Type'] = card.get('rel_type') or '-'
                enriched_row['Door / House No'] = card.get('door_no') or '-'
                enriched_row['Age'] = str(card.get('age')) if card.get('age') else '-'
                
                gen = card.get('gender')
                if not gen and card.get('rel_type') == 'Husband':
                    gen = 'Female'
                enriched_row['Gender'] = gen or '-'
                
                enriched_row['2025 Booth Serial No'] = str(card.get('booth_sno')) if card.get('booth_sno') else '-'
                enriched_row['2025 Assembly Part No (Baseline)'] = card.get('part_no', '-')
                enriched_row['Match Confidence'] = match_type
            else:
                unmatched_count += 1
                enriched_row['Father / Husband / Guardian Name'] = '-'
                enriched_row['Relationship Type'] = '-'
                enriched_row['Door / House No'] = '-'
                enriched_row['Age'] = '-'
                enriched_row['Gender'] = '-'
                enriched_row['2025 Booth Serial No'] = '-'
                enriched_row['2025 Assembly Part No (Baseline)'] = '-'
                enriched_row['Match Confidence'] = 'Unmatched in Roll Scan'

            enriched_list.append(enriched_row)

        audit_report = {
            'total_ground_truth': len(self.ground_truth),
            'exact_epic_matches': exact_count,
            'fuzzy_or_name_matches': fuzzy_count,
            'total_resolved': exact_count + fuzzy_count,
            'unmatched': unmatched_count,
            'resolution_rate': f"{(exact_count + fuzzy_count) / len(self.ground_truth) * 100:.2f}%"
        }

        return enriched_list, audit_report
