"""
Test script for verifying enhanced dot-matrix EPIC recovery logic
against all 799 cards of Part 001.
"""

import os
import sys
import json
import re

CACHE_PATH = r"C:\Users\vamsi\.gemini\antigravity\scratch\v_ocr\deip_cache_part001_full_ac38_part_1.json"

epic_char_subs = {
    'O': '0', 'o': '0', 'Q': '0', 'D': '0', 'Z': '2', 'I': '1', 'i': '1',
    'l': '1', '|': '1', 'T': '1', 'B': '8', 'S': '5', 's': '5', 'E': '5',
    'G': '6', 'A': '4', 'U': '0', '/': '7', '?': '7', 'P': '9', 'C': '9', 'R': '8'
}

def enhanced_normalize(cand):
    if not cand:
        return None
    s = str(cand).strip().upper()
    s = re.sub(r'[^\x00-\x7F]+', '', s)
    s = re.sub(r'[|\[\]\(\)\{\},:;\'\"`_~]+', ' ', s).strip()
    s = re.sub(r'^\s*[0-9ILF]{1,4}\s+', '', s)
    cand = s.replace(' ', '').replace('-', '')

    # 1. Standardize dot-matrix fused prefixes & detach border noise
    cand = re.sub(r'^(WION|LION|MION|HION|TION|VION|LLON|IION)', 'UON', cand)
    cand = re.sub(r'^(W0N|U0N|V0N|UQN|L0N)', 'UON', cand)
    cand = re.sub(r'^[A-Z0-9]{1,2}(UON|WON|YOU|IMZ|BCK|GHZ|WUZ|CVB|FXF)', r'\1', cand)
    cand = re.sub(r'^(YOUM|YOUN)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{5}$)', 'YOU14', cand)
    cand = re.sub(r'^(YOUN|YOUT|YOUI|YOUL)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{6}$)', 'YOU1', cand)
    cand = re.sub(r'^(YOUU|YOUI|YOUN|YOUW|YOUL|YOUJ|YOUPR|YOUP|YOQU|YOUT)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{7,8}$)', 'YOU', cand)
    cand = re.sub(r'^(Y0U|YQU|VOU|YDU|YOO|YCU|YGU|T0U|TOU)', 'YOU', cand)
    cand = re.sub(r'^(BOCK|B0CK|8CK|BCR|BGK|BCX|ECK|RCK|BOK)', 'BCK', cand)
    cand = re.sub(r'^(IMZN|IMZT|IMZI)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{6}$)', 'IMZ1', cand)
    cand = re.sub(r'^(IM2Z|IMUZ|IMIZ|IMLZ|INZ|1MZ|LMZ|TMZ|1M2Z|LM2Z|JMZ|JM2Z|MZ|IM|NMZ)', 'IMZ', cand)
    cand = re.sub(r'^(GH2|GZ|CHZ)', 'GHZ', cand)
    cand = re.sub(r'^(WUZM|WUZN|WLZM|WIZM)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{5}$)', 'WUZ14', cand)
    cand = re.sub(r'^(WLU2Z|WUI2Z|WIJ2Z|WU2Z|WLUZ|WUIZ|WLU2|WUI2|WLZ|WIZ|WSZ|WWZ|WTZ|WLU|WWU|WIU|WUU|WLI|WII|WLE|WUD|WUS|WUI|WU2|WU7|WU\?|WI\?|WL\?|WIJ|WHI|WUA|WHU|WIE|WIL|LUZ|WUR|WEZ|WIT|WLS|WLJ|WAS|WTI|VUZ|WLO|WLA|WDU|WLL|WUC|WWS|WHZ|WOS)', 'WUZ', cand)

    # 2. If length > 10, extract embedded candidate pattern
    if len(cand) > 10:
        m = re.search(r'([A-Z]{3}[0-9OQDZITBSGAUEPCR\?/\-]{6,8})', cand)
        if m:
            cand = m.group(1)

    if len(cand) < 9 or len(cand) > 12:
        return None

    prefix = cand[:3]
    if not (prefix.isascii() and prefix.isalpha() and len(prefix) == 3):
        return None

    raw_suffix = cand[3:].strip('|/[]().,:;\'"`_ )')
    cleaned_suffix = []
    for ch in raw_suffix:
        if ch.isdigit():
            cleaned_suffix.append(ch)
        elif ch in epic_char_subs:
            cleaned_suffix.append(epic_char_subs[ch])
        else:
            return None

    suffix_str = ''.join(cleaned_suffix)
    if len(suffix_str) == 7:
        return prefix + suffix_str
    elif len(suffix_str) == 6:
        return prefix + '0' + suffix_str
    elif len(suffix_str) == 8:
        if suffix_str[0] in ('1', '9', '0', '2'):
            return prefix + suffix_str[1:]
        elif suffix_str[-1] in ('1', '0'):
            return prefix + suffix_str[:-1]
    return None


def run_test():
    with open(CACHE_PATH, 'r', encoding='utf-8') as f:
        cards = json.load(f)

    valid_count = 0
    recovered_samples = []

    for r in cards:
        orig_epic = r.get('epic_no', '-')
        dump = r.get('raw_ocr_dump', '')
        first_lines = dump.split('\n')[:3]
        found = None
        for line in first_lines:
            # Try token by token
            for tok in line.strip().split():
                norm = enhanced_normalize(tok)
                if norm:
                    found = norm
                    break
            # Try whole line
            if not found:
                norm = enhanced_normalize(line)
                if norm:
                    found = norm
            if found:
                break

        if found:
            valid_count += 1
            if orig_epic in ('-', ''):
                recovered_samples.append({
                    'sno': r.get('booth_sno'),
                    'recovered_epic': found,
                    'raw_line': first_lines[0]
                })

    print(f"Total Cards: {len(cards)}")
    print(f"Total Valid EPICs with Recommendation: {valid_count} / {len(cards)} ({valid_count/len(cards)*100:.2f}%)")
    print(f"Newly Recovered EPICs from previously blank cards: {len(recovered_samples)}")
    print("\nSample Newly Recovered EPICs:")
    for s in recovered_samples[:10]:
        print(f"  SNO #{s['sno']:03d} -> Recovered: {s['recovered_epic']} (from raw: {repr(s['raw_line'])})")

if __name__ == '__main__':
    run_test()
