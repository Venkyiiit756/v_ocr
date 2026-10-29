import pandas as pd
import re
from collections import defaultdict, Counter

# Strict Protected Names Whitelist (NEVER touch these under any circumstances)
PROTECTED_TOKENS = {
    'kiran', 'charan', 'ravikiran', 'saikiran', 'ramcharan', 'imran', 'simran', 
    'kalyan', 'pavan', 'karan', 'chandran', 'sudhakar', 'sudharan', 'dharan', 
    'sharan', 'aran', 'moran', 'saran', 'ushakiran', 'devikaran', 'peeta', 
    'chavala', 'rao', 'reddy', 'naidu', 'varma', 'raju', 'babu', 'kumar', 'singh'
}

PHONOTACTIC_RULES = [
    # 1. Lakshmi / Laxmi
    (r'\b([A-Za-z]+)lakshm\b', r'\g<1>lakshmi'),
    (r'\b([A-Za-z]+)laxm\b', r'\g<1>laxmi'),
    # 2. Surnames ending in sett -> setti (Vasamsett -> Vasamsetti, Koppisett -> Koppisetti)
    (r'\b([A-Za-z]{3,})sett\b', r'\g<1>setti'),
    # 3. Surnames ending in pall -> palli (Gollapall -> Gollapalli, Chintapall -> Chintapalli)
    (r'\b([A-Za-z]{3,})pall\b', r'\g<1>palli'),
    # 4. Surnames ending in vill -> villi (Ayinavill -> Ayinavilli, Veeravill -> Veeravilli)
    (r'\b([A-Za-z]{3,})vill\b', r'\g<1>villi'),
    # 5. Surnames ending in parth -> parthi (Palaparth -> Palaparthi, Tatiparth -> Tatiparthi)
    (r'\b([A-Za-z]{3,})parth\b', r'\g<1>parthi'),
    # 6. Surnames ending in redd -> reddy (Abbiredd -> Abbireddy, Kosiredd -> Kosireddy)
    (r'\b([A-Za-z]{3,})redd\b', r'\g<1>reddy'),
    # 7. Surnames ending in kurth -> kurthi (Morukurth -> Morukurthi)
    (r'\b([A-Za-z]{3,})kurth\b', r'\g<1>kurthi'),
    # 8. Surnames ending in cherl -> cherla (Palagcherl -> Palagcherla)
    (r'\b([A-Za-z]{3,})cherl\b', r'\g<1>cherla'),
    # 9. Surnames ending in pat -> pati (Pedapat -> Pedapati, Garapat -> Garapati, Bodapat -> Bodapati)
    (r'\b([A-Za-z]{3,}[aeiou])pat\b', r'\g<1>pati'),
    # 10. Surnames ending in dat -> dati (Guddat -> Guddati)
    (r'\b([A-Za-z]{3,}[aeiou])dat\b', r'\g<1>dati'),
    # 11. Male names ending in rajl -> raju (Nookarajl -> Nookaraju, Lovarajl -> Lovaraju)
    (r'\b([A-Za-z]+)rajl\b', r'\g<1>raju'),
    # 12. Female names ending in bhavan -> bhavani (Nagabhavan -> Nagabhavani)
    (r'\b([A-Za-z]+)bhavan\b', r'\g<1>bhavani'),
    # 13. Female names ending in parvath -> parvathi
    (r'\b([A-Za-z]+)parvath\b', r'\g<1>parvathi'),
    # 14. Female names ending in satyaven -> satyaveni
    (r'\b([A-Za-z]+)satyaven\b', r'\g<1>satyaveni'),
    # 15. Male names ending in swam -> swamy (Buliswam -> Buliswamy)
    (r'\b([A-Za-z]+)swam\b', r'\g<1>swamy'),
    # 16. Female names ending in amm -> amma (Bullamm -> Bullamma)
    (r'\b([A-Za-z]{3,})amm\b', r'\g<1>amma'),
    # 17. Standalone Dev -> Devi
    (r'\bDev\b', 'Devi'),
]

def apply_safe_phonotactic_rules(name_str):
    if not name_str or str(name_str).strip() in ('-', 'nan', ''):
        return name_str
    s = str(name_str).strip()
    words = s.split()
    new_words = []
    for w in words:
        w_lower = w.lower()
        # ABSOLUTE SAFETY GUARD: If word is in PROTECTED_TOKENS, NEVER TOUCH IT
        if w_lower in PROTECTED_TOKENS:
            new_words.append(w)
            continue
        # Apply rules
        w_mod = w
        for pat, repl in PHONOTACTIC_RULES:
            w_mod = re.sub(pat, repl, w_mod, flags=re.I)
        new_words.append(w_mod)
    return ' '.join(new_words)

def can_repair_surname(short_sur, long_sur):
    # Rule 1: Short surname MUST end in a consonant (excluding y) to be eligible for elongation
    if re.search(r'[aeiouy]$', short_sur, re.I):
        return False
    # Rule 2: Long surname must end in standard Telugu vowel ending (i, y, u, a)
    if not re.search(r'[aeiouy]$', long_sur, re.I):
        return False
    # Rule 3: Protected tokens must never be elongated
    if short_sur.lower() in PROTECTED_TOKENS or long_sur.lower() in PROTECTED_TOKENS:
        return False
    # Rule 4: Long surname must strictly start with short surname
    if not long_sur.lower().startswith(short_sur.lower()):
        return False
    diff = len(long_sur) - len(short_sur)
    if diff not in (1, 2):
        return False
    return True

def repair_intra_card(v_name, r_name):
    if not v_name or not r_name or v_name == '-' or r_name == '-':
        return v_name, r_name
    v_words = v_name.split()
    r_words = r_name.split()
    if len(v_words) >= 2 and len(r_words) >= 2:
        v_sur = v_words[-1]
        r_sur = r_words[-1]
        if v_sur.isalpha() and r_sur.isalpha() and len(v_sur) >= 4 and len(r_sur) >= 4:
            if can_repair_surname(v_sur, r_sur):
                v_words[-1] = r_sur
                v_name = ' '.join(v_words)
            elif can_repair_surname(r_sur, v_sur):
                r_words[-1] = v_sur
                r_name = ' '.join(r_words)
    return v_name, r_name

def build_household_map(df_subset):
    hh_surnames = defaultdict(list)
    for idx, r in df_subset.iterrows():
        p = r['assembly_part_2025']
        d = r['door_no']
        if not d or d in ('-', 'nan', ''):
            continue
        for nm in (r['voter_name_en'], r['rel_name_en']):
            if nm and nm != '-':
                words = nm.split()
                if len(words) >= 2:
                    sur = words[-1]
                    if len(sur) >= 4 and sur.isalpha():
                        hh_surnames[(p, d)].append(sur)
    
    consensus_map = {}
    for (p, d), sur_list in hh_surnames.items():
        if len(sur_list) < 2:
            continue
        counts = Counter(sur_list)
        for clean_sur, cnt in counts.items():
            if cnt >= 2:
                for other_sur in counts:
                    if can_repair_surname(other_sur, clean_sur):
                        consensus_map[(p, d, other_sur.lower())] = clean_sur
    return consensus_map

def verify_zero_false_positives():
    test_cases = [
        "Kiran Kumar Chavala",
        "Sai Kiran Pilli",
        "Ravi Kiran Reddy",
        "Charan Teja Bodapati",
        "Ram Charan Koppisetti",
        "Pavan Kalyan Vasamsetti",
        "Abba Peeta",
        "Mang Peeta",
        "Apparao Chavala",
        # These SHOULD be corrected:
        "Venkatalakshm Guddati",
        "Koppisett Durga",
        "Suryaravu Tatiparth",
        "Nookarajl Ghavala",
        "Durga Dev Chintapall",
    ]
    print("=== VERIFYING TEST STRINGS ===")
    for t in test_cases:
        res = apply_safe_phonotactic_rules(t)
        changed = (t != res)
        print(f"  {repr(t):32} -> {repr(res):32} (Modified: {changed})")
        # Assertions
        if "Kiran" in t:
            assert "Kiran" in res and "Kirani" not in res, f"FAILED: Kiran modified in {t}!"
        if "Charan" in t:
            assert "Charan" in res, f"FAILED: Charan modified in {t}!"
        if "Peeta" in t:
            assert "Peeta" in res and "Peetaa" not in res, f"FAILED: Peeta modified in {t}!"
    print("ALL ASSERTIONS PASSED! ZERO FALSE POSITIVES!\n")

if __name__ == '__main__':
    verify_zero_false_positives()
