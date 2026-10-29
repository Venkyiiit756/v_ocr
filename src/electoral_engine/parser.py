"""
Structured Field Extractor for Individual Voter Cards.
Extracts Serial No, EPIC, Voter Name, Relative Name, Relation Type,
Door/House Number, Age, and Gender from raw OCR text.
"""

import re

class VoterCardParser:
    def __init__(self):
        # Common OCR character confusions in Indian EPIC numeric suffixes
        self.epic_char_subs = {
            'O': '0',
            'o': '0',
            'Q': '0',
            'D': '0',
            'Z': '2',
            'I': '1',
            'i': '1',
            'l': '1',
            '|': '1',
            'T': '1',
            'B': '8',
            'S': '5',
            's': '5',
            'E': '5',
            'G': '6',
            'A': '4',
            'U': '0',
            '/': '7',
            '?': '7',
            'P': '9',
            'C': '9',
            'R': '8'
        }

    def normalize_epic_candidate(self, cand):
        if not cand:
            return None
        s = str(cand).strip()
        # Strip any non-ASCII replacement characters (e.g. \ufffd)
        s = re.sub(r'[^\x00-\x7F]+', '', s)
        # Lowercase 'd' or 'a' inside numeric suffix is a common OCR confusion for '4'
        s = re.sub(r'(?<=[0-9])d(?=[0-9])', '4', s)
        s = s.upper()
        # Strip border symbols and whitespace first so '| 1063' becomes '1063'
        s = re.sub(r'[|\[\]\(\)\{\},:;\'\"`_~]+', ' ', s).strip()
        # Strip leading serial numbers if present on the same line
        s = re.sub(r'^\s*[0-9ILF]{1,4}\s+', '', s)
        cand = s.replace(' ', '').replace('-', '')

        # Fix leading noise char before WU + 7 digits (e.g. SWU2456937, JWU2456291 -> WUZ2456937)
        cand = re.sub(r'^[A-Z]WU(?=[0-9]{7}$)', 'WUZ', cand)

        # Normalize Pithapuram (AC 37) 'YOU' and 'BCK' OCR prefix stretches & kerning fusions
        # Kerning fusion: 'YOU14' + 5 digits fused into 'YOUM' or 'YOUN' + 5 digits
        cand = re.sub(
            r'^(YOUM|YOUN)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{5}$)',
            'YOU14',
            cand
        )
        # Kerning fusion: 'YOU1' + 6 digits fused into 'YOUN'/'YOUT'/'YOUI'/'YOUL' + 6 digits
        cand = re.sub(
            r'^(YOUN|YOUT|YOUI|YOUL)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{6}$)',
            'YOU1',
            cand
        )
        cand = re.sub(
            r'^(YOUU|YOUI|YOUN|YOUW|YOUL|YOUJ|YOUPR|YOUP|YOQU|YOUT)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{7,8}$)',
            'YOU',
            cand
        )
        cand = re.sub(
            r'^(Y0U|YQU|VOU|YDU|YOO|YCU|YGU|T0U|TOU)',
            'YOU',
            cand
        )
        cand = re.sub(r'^(OU|0U|QU|YU)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{7,8}$)', 'YOU', cand)
        cand = re.sub(r'^(BOCK|B0CK|8CK|BCR|BGK|BCX|ECK|RCK|BOK)', 'BCK', cand)

        # Normalize Kakinada Rural (AC 38) 'IMZ', 'UON', 'GHZ' OCR prefix stretches
        cand = re.sub(
            r'^(IMZN|IMZT|IMZI)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{6}$)',
            'IMZ1',
            cand
        )
        cand = re.sub(
            r'^(IM2Z|IMUZ|IMIZ|IMLZ|INZ|1MZ|LMZ|TMZ|1M2Z|LM2Z|JMZ|JM2Z|MZ|IM|NMZ)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{7,8}$)',
            'IMZ',
            cand
        )
        cand = re.sub(r'^(GH2|GZ|CHZ)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{7}$)', 'GHZ', cand)
        cand = re.sub(r'^(U0N|VON|UQN)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{7}$)', 'UON', cand)

        # Normalize Peddapuram (AC 39) & general ECI OCR prefix stretches
        cand = re.sub(
            r'^(WUZM|WUZN|WLZM|WIZM)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{5}$)',
            'WUZ14',
            cand
        )
        cand = re.sub(
            r'^(WUZN|WUZT|WUZI|WUZL|WLZN|WLZT|WIZN|WIZT)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{6}$)',
            'WUZ1',
            cand
        )
        cand = re.sub(
            r'^(WLU2Z|WUI2Z|WIJ2Z|WU2Z|WLUZ|WUIZ|WLU2|WUI2|WLZ|WIZ|WSZ|WWZ|WTZ|WLU|WWU|WIU|WUU|WLI|WII|WLE|WUD|WUS|WUI|WU2|WU7|WU\?|WI\?|WL\?|WIJ|WHI|WUA|WHU|WIE|WIL|LUZ|WUR|WEZ|WIT|WLS|WLJ|WAS|WTI|VUZ|WLO|WLA|WDU|WLL|WUC|WWS|WHZ|WOS)(?=[0-9OQDZI|lTBSGAU/\?EPCR]{7,8}$)',
            'WUZ',
            cand
        )
        cand = re.sub(r'^(WU|WL|WI|W2|WZ|W)(?=[0-9TILDQOBZSGAU/\?EPCR]{7}$)', 'WUZ', cand)
        cand = re.sub(r'^(WULF|WUIF|WLF|WIF)', 'WUF', cand)
        cand = re.sub(r'^(H5F|H8F|HBF|MSF|M5F|HSE|HEF|HOF|HGF|HSR|HER|NSF|RSF|LSF|HSI)', 'HSF', cand)
        cand = re.sub(r'^(OVB|GVB)', 'CVB', cand)
        cand = re.sub(r'^(FRF|FAF|FSF|FMF)', 'FXF', cand)
        cand = re.sub(r'^(=GA|5GA|\$GA)', 'SGA', cand)
        cand = re.sub(r'^(BON|=QN)', 'BQN', cand)

        if len(cand) < 9 or len(cand) > 13:
            return None

        # Guard 1: Must have strict 3 ASCII alpha prefix
        prefix = cand[:3]
        if not (prefix.isascii() and prefix.isalpha() and len(prefix) == 3):
            return None

        # Clean 7-digit numeric suffix
        raw_suffix = cand[3:].strip('|/[]().,:;\'"`_ )')

        # Collapse adjacent digit+lookalike-letter OCR double-reads ONLY when suffix is 8 chars
        # (e.g. YOU2Z345239 -> YOU2345239, YOU0Q895120 -> YOU0895120, YOU14A16474 -> YOU1416474)
        if len(raw_suffix) == 8:
            for twin, single in (
                ('?7', '7'), ('/7', '7'), ('7?', '7'), ('7/', '7'),
                ('2Z', '2'), ('Z2', '2'),
                ('0Q', '0'), ('Q0', '0'), ('0O', '0'), ('O0', '0'), ('0D', '0'), ('D0', '0'),
                ('4A', '4'), ('A4', '4'),
                ('1I', '1'), ('I1', '1'), ('1L', '1'), ('L1', '1'),
                ('5S', '5'), ('S5', '5'),
                ('8B', '8'), ('B8', '8'),
                ('6G', '6'), ('G6', '6')
            ):
                if twin in raw_suffix:
                    raw_suffix = raw_suffix.replace(twin, single, 1)
                    break

        # Guard 2 (Anti-False-Positive): Require genuine numeric digits (0-9) before char substitution
        # (2+ digits if prefix is a known ECI series prefix, 4+ digits otherwise) so words never become fake EPICs
        min_digits = 2 if prefix in ('YOU', 'BCK', 'IMZ', 'GHZ', 'UON', 'WUZ', 'WUF', 'HSF', 'CVB', 'FXF', 'SGA', 'BQN') else 4
        if sum(1 for ch in raw_suffix if ch.isdigit()) < min_digits:
            return None

        cleaned_suffix = []
        for ch in raw_suffix:
            if ch.isdigit():
                cleaned_suffix.append(ch)
            elif ch in self.epic_char_subs:
                cleaned_suffix.append(self.epic_char_subs[ch])
            elif ch in '.,:;\'"`_ ()[]{}/\\':
                continue
            else:
                return None

        suffix_str = ''.join(cleaned_suffix)
        if len(suffix_str) == 7:
            return prefix + suffix_str
        elif len(suffix_str) == 8:
            if suffix_str[0] in ('1', '9', '0', '2'):
                return prefix + suffix_str[1:]
            elif suffix_str[-1] in ('1', '0'):
                return prefix + suffix_str[:-1]

        return None

    def clean_name(self, raw_str):
        if not raw_str:
            return ''
        n = str(raw_str).strip()
        # Fix leading )4 or )A OCR artifact for 'A' (e.g., ')4Kkamma' -> 'Akkamma')
        n = re.sub(r'^[\)\]\(\[1\|!]+4(?=[A-Za-z])', 'A', n)
        n = re.sub(r'^[\)\]\(\[0-9\|!:\+\-\.\,;\?~`\'\"_]+', '', n).strip()
        # Strip leading role prefixes and common OCR variations of Name:
        n = re.sub(r'^(Father|Fathar|Fether|Husband|Hushend|Hushand|Husban|Mother|Mothar|Mether|Other|Otners|Othars|Otliers|Guardian|Name|Mame|Namie|Narne|Narre|Nama|Narme|Namet|Warne|Nate|Nane|Peru)[s\'’]*\s*[:*=\?;\+\s\-]*', '', n, flags=re.I)
        n = re.sub(r'^(Father|Fathar|Fether|Husband|Hushend|Hushand|Husban|Mother|Mothar|Mether|Other|Otners|Othars|Otliers|Guardian|Name|Mame|Namie|Narne|Narre|Nama|Narme|Namet|Warne|Nate|Nane)[s\'’]*\s*[:*=\?;\+\s\-]*', '', n, flags=re.I)
        n = re.sub(r'^t\s+(?=[A-Z]{2,})', '', n)

        # Strip trailing and mid-string noise labels
        n = re.sub(r'\b(Photo|Available|Fhoto|House|Howse|Age|Gender|Ganclar|Gander|Male|Female)\b.*', '', n, flags=re.I)
        n = re.sub(
            r'\b(Father|Fathar|Fether|Husband|Hushend|Hushand|Mother|Mothar|Guardian|Name|Mame|Namie|Narne|Narre|Nama|Narme|Namet|Warne|Nate|Nane|House|Howse|Number|Photo|Available|Age|Gender|Gencler|Ganclar|Gander)[s\'’]*\s*[:*=\?;\+\-]*\s*',
            ' ',
            n,
            flags=re.I
        )

        # Word-ending OCR fixes: ! or | or 1 at end of word -> I (e.g. BOD! -> BODI)
        n = re.sub(r'([A-Za-z]+)[!|1]\b', r'\g<1>I', n)

        # Common transliteration OCR swaps in Telugu voter rolls
        n = re.sub(r'([A-Za-z]+)ra[qg]\b', r'\g<1>rao', n, flags=re.I)
        n = re.sub(r'([A-Za-z]+)babl[i]?\b', r'\g<1>babu', n, flags=re.I)
        n = re.sub(r'\b(RAG|RAQ)\b', 'RAO', n, flags=re.I)
        n = re.sub(r'\b(BABL|BABLI)\b', 'BABU', n, flags=re.I)
        n = re.sub(r'\bBALAI\b', 'BALAJI', n, flags=re.I)
        n = re.sub(r'\bLakghmi\b', 'Lakshmi', n, flags=re.I)
        n = re.sub(r'\bLaghmi\b', 'Lakshmi', n, flags=re.I)

        # Strip noise apostrophes inside or at edges of words (e.g. Veeraswam'Y -> Veeraswamy, Dorayy'A -> Dorayya)
        n = re.sub(r"['`]([A-Z])\b", lambda m: m.group(1).lower(), n)
        n = re.sub(r"['`]([A-Z])([a-z])", lambda m: m.group(1).lower() + m.group(2), n)
        n = re.sub(r"['`]([A-Za-z])", r"\1", n)
        n = re.sub(r"([A-Za-z])['`]", r"\1", n)

        # Strip intra-word splatter dots (e.g. Sathy.Am -> Satyam, App.Anna -> Appanna)
        n = re.sub(r'(?<=[A-Za-z]{2})\.(?=[A-Za-z]{2})', '', n)
        n = re.sub(r'(?<=[A-Za-z])\.(?=[A-Za-z]{3})', '', n)

        # Unfuse glued initial prefixes (e.g. Vvsatyanarayan -> V V Satyanarayan)
        n = re.sub(r'\bvv([a-z]{3,})\b', r'V V \1', n, flags=re.I)

        # Protected tokens list to prevent any false positives (e.g. Kiran -> Kirani, Charan, Peeta)
        protected_tokens = {
            'kiran', 'charan', 'ravikiran', 'saikiran', 'ramcharan', 'imran', 'simran',
            'kalyan', 'pavan', 'karan', 'chandran', 'sudhakar', 'sudharan', 'dharan',
            'sharan', 'aran', 'moran', 'saran', 'ushakiran', 'devikaran', 'peeta',
            'chavala', 'rao', 'reddy', 'naidu', 'varma', 'raju', 'babu', 'singh',
            'chandra', 'nageswara', 'nagendra', 'gundra', 'kakara', 'sunkara', 'shubhadra',
            'sriram', 'balaram', 'ram', 'shyam', 'abhiram', 'parasuram', 'jayaram', 'tara',
            'indira', 'surekha', 'rekha', 'kavitha', 'anitha', 'sunitha', 'geetha', 'seetha',
            'prasad', 'durgaprasad', 'ramaprasad', 'sivaprasad', 'varaprasad', 'naveen',
            'praveen', 'sharad', 'bharath', 'hemanth', 'sreekanth', 'siddharth',
            'navya', 'kavya', 'sravya', 'bhavya'
        }

        # Safe Telugu phonotactic syllable completions on word tokens
        words = n.split()
        safe_words = []
        for w in words:
            if w.lower() in protected_tokens:
                safe_words.append(w)
                continue
            # Glyph repairs: cl -> d (prasacl -> prasad, muppicl -> muppidi, kacliyala -> kadiyala)
            if 'cl' in w.lower():
                w = re.sub(r'cl', 'd', w, flags=re.I)
                if w.lower() in protected_tokens:
                    safe_words.append(w)
                    continue
            # Kerning repairs: rarn... -> ram..., arnma -> amma
            w = re.sub(r'^rarn', 'ram', w, flags=re.I)
            w = re.sub(r'arnma\b', 'amma', w, flags=re.I)
            # Telugu surname consonant stems
            w = re.sub(r'([A-Za-z]+)lll\b', r'\g<1>lli', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})sett\b', r'\g<1>setti', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})pall\b', r'\g<1>palli', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})vill\b', r'\g<1>villi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})bill\b', r'\g<1>billi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})pill\b', r'\g<1>pilli', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})parth\b', r'\g<1>parthi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})redd\b', r'\g<1>reddy', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})kurth\b', r'\g<1>kurthi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,})cherl\b', r'\g<1>cherla', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,}[aeiou])pat\b', r'\g<1>pati', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,}[aeiou])dat\b', r'\g<1>dati', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,}(?:mupp|mam|bomm|umm|sal|karn|pern))id\b', r'\g<1>idi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,}[aeiou])pud\b', r'\g<1>pudi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,}[aeiou])kot\b', r'\g<1>koti', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,}[aeiou])gant\b', r'\g<1>ganti', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{2,}[aeiou])bant\b', r'\g<1>banti', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]*(?:pasupul|pall|dang|pek|kond|ol|kon|domm|gand|tol|yel|gant|kan|gandr|pal|ak|mel|thol|moll|kat|yarlagadd|gollapul))et\b', r'\g<1>eti', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]*[aeiou])rapl(?:i)?\b', r'\g<1>rapalli', w, flags=re.I)
            w = re.sub(r'\bpeddint\b', 'Peddinti', w, flags=re.I)
            w = re.sub(r'\bmuthint\b', 'Muthinti', w, flags=re.I)
            w = re.sub(r'\bbandarl\b', 'Bandaru', w, flags=re.I)
            w = re.sub(r'\bmangatayarl\b', 'Mangatayaru', w, flags=re.I)
            w = re.sub(r'\bband\b', 'Bandi', w, flags=re.I)
            w = re.sub(r'\bdodd\b', 'Doddi', w, flags=re.I)
            w = re.sub(r'\bmedish\b', 'Medisetti', w, flags=re.I)
            w = re.sub(r'\bkolll?\b', 'Kolli', w, flags=re.I)
            w = re.sub(r'\bmoll\b', 'Molli', w, flags=re.I)
            # Raju typos
            w = re.sub(r'\b([A-Za-z]+)raiu\b', r'\g<1>raju', w, flags=re.I)
            w = re.sub(r'\braiu\b', 'Raju', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)rajlu\b', r'\g<1>raju', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)rajl\b', r'\g<1>raju', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)rajtu\b', r'\g<1>raju', w, flags=re.I)
            # Babu typos
            w = re.sub(r'\b([A-Za-z]+)bablu\b', r'\g<1>babu', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)babl\b', r'\g<1>babu', w, flags=re.I)
            # Rao typos
            w = re.sub(r'\b(rad|rac)\b', 'Rao', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]*(?:wa|pa|ba|dra|tha|na|ga|ya|la|ma|dha|sa|ka|ra))ra[dc]\b', r'\g<1>rao', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)rao[qge]\b', r'\g<1>rao', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]*(?:bhadra|prakasha|maheswara|eswara|nagendra|ramalinga))r\b', r'\g<1>rao', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{4,})murth?\b', r'\g<1>murthy', w, flags=re.I)
            # Standard female & male suffixes
            w = re.sub(r'\b([A-Za-z]+)lakshm\b', r'\g<1>lakshmi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)laxm\b', r'\g<1>laxmi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)bhavan\b', r'\g<1>bhavani', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)parvath\b', r'\g<1>parvathi', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]*(?:satya|krishna|durga|manga|ganga))ven\b', r'\g<1>veni', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]+)swam\b', r'\g<1>swamy', w, flags=re.I)
            w = re.sub(r'\b([A-Za-z]{3,})amm\b', r'\g<1>amma', w, flags=re.I)
            w = re.sub(r'\bDev\b', 'Devi', w)
            w = re.sub(r'\bJyoth\b', 'Jyothi', w, flags=re.I)
            w = re.sub(r'\bTulas\b', 'Tulasi', w, flags=re.I)
            w = re.sub(r'\bAmmaj\b', 'Ammaji', w, flags=re.I)
            w = re.sub(r'\bJhans\b', 'Jhansi', w, flags=re.I)
            # Telugu Ch -> Gh confusion
            w = re.sub(r'\bgh(inna|akram|andrarao|okka|alla|andra|intapalli|intapall|ittibabu|akra|antibabu|innarao|akramma|ina|elluri|akradhar|akrarao|innari|avala|eduluri|odisetti|odisetty|epala|eekatla|ikatla|ikkala|ukkala|andaka|inaapparao|innaiah)\b', r'ch\g<1>', w, flags=re.I)
            safe_words.append(w)
            w = re.sub(r'\bAmmaj\b', 'Ammaji', w, flags=re.I)
            w = re.sub(r'\bJhans\b', 'Jhansi', w, flags=re.I)
            # Telugu Ch -> Gh confusion
            w = re.sub(r'\bgh(inna|akram|andrarao|okka|alla|andra|intapalli|intapall|ittibabu|akra|antibabu|innarao|akramma|ina|elluri|akradhar|akrarao|innari|avala|eduluri|odisetti|odisetty|epala|eekatla|ikatla|ikkala|ukkala|andaka|inaapparao|innaiah)\b', r'ch\g<1>', w, flags=re.I)
            safe_words.append(w)
        n = ' '.join(safe_words)

        # Keep only valid name characters
        n = re.sub(r'[^A-Za-z\s\.\']+', ' ', n)
        n = re.sub(r'\s+', ' ', n).strip(' .-')
        if len(n) < 2 or not any(ch.isalpha() for ch in n):
            return ''
        return n

    def clean_door(self, raw_door):
        if not raw_door:
            return ''
        d = str(raw_door).strip()
        d = re.sub(r'^(?:[HhlI1|]?[o0eau]us[ea]?|Howse|Hous|Inti|D\.?No|H\.?No)\s*(?:Nu[rmn]{1,3}be?r|Numbar|Num|No)?\s*[:*+=;>?\}\]\-\.\'\"it!|/\s]+', '', d, flags=re.I)
        d = re.sub(r'^(?:Nu[rmn]{1,3}be?r|Numbar|Num|No)\s*[:*+=;>?\}\]\-\.\'\"it!|/\s]*', '', d, flags=re.I)
        d = re.sub(r'\b(Photo|Available|Fhoto|Age|Gender|Gencler|Ganclar|Gander|beside|near|opp|opposite)\b.*', '', d, flags=re.I)
        d = d.replace('¢', '-').replace('°', '-')
        d = re.sub(r'\s*([\/\-])\s*', r'\1', d)
        d = re.sub(r'[\?\*!\+=_\[\]#|~\\<>\{\}\$§©@•\ufffd\'\"]+', '', d)
        d = d.strip(' :|+-./')
        if not any(ch.isdigit() for ch in d):
            return ''
        return d

    def parse_card(self, ocr_text, fallback_sno=None):
        """
        Parses OCR text of an isolated voter card into a structured dictionary.
        """
        lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]
        full_text = '\n'.join(lines)

        # 1. Booth Serial Number & EPIC No
        extracted_sno = fallback_sno
        extracted_epic = None

        for hdr_line in lines[:2]:
            norm = self.normalize_epic_candidate(hdr_line)
            if norm:
                extracted_epic = norm
                break

        header_m = re.search(r'^\s*([0-9il]{1,4})\s+([A-Z0-9=$\?/\s]{8,16})', full_text, re.M | re.I)
        if header_m:
            try:
                raw_sno = header_m.group(1).replace('l', '1').replace('i', '1')
                extracted_sno = int(raw_sno)
            except ValueError:
                pass
            if not extracted_epic:
                extracted_epic = self.normalize_epic_candidate(header_m.group(2))

        if not extracted_epic:
            tokens = re.findall(r'[A-Z0-9=$\?]{2,5}(?:\s+[0-9A-Za-z/\?]{2,8}){1,2}|[A-Z0-9=$\?]{3,5}\s?[0-9A-Za-z/\?]{6,9}', full_text)
            for t in tokens:
                norm = self.normalize_epic_candidate(t)
                if norm:
                    extracted_epic = norm
                    break

        # 2. Voter Name
        voter_name = ''
        for idx_l, line in enumerate(lines):
            if re.search(r'\b(Father|Fathar|Fether|Husband|Hushend|Mother|Mothar|Other|Guardian)[s\'’]*\b', line, re.I):
                continue
            nm = re.search(r'\b(?:Name|Mame|Namie|Narne|Narre|Nama|Narme|Namet|Nane|Peru|Voter\s*Name)\s*[:*+=;>\?\-\s]*(.*)', line, re.I)
            if nm:
                cand_name = self.clean_name(nm.group(1))
                if not cand_name and idx_l + 1 < len(lines):
                    nxt = lines[idx_l + 1]
                    if not re.search(r'\b(Father|Fathar|Fether|Husband|Hushend|Mother|Mothar|Other|Guardian|House|Howse|Age|Gender)\b', nxt, re.I):
                        cand_name = self.clean_name(nxt)
                if cand_name:
                    voter_name = cand_name
                    break

        # 3. Relative Name & Relationship Type
        rel_type = ''
        rel_name = ''
        rel_m = re.search(
            r'(Father|Fathar|Fether|Husband|Hushend|Hushand|Husban|Mother|Mothar|Mether|Other|Otners|Othars|Otliers|Guardian)[s\'’]*(?:\s*(?:Name|Mame|Namie|Narne|Narre|Nama|Narme|Namet|Warne|Nate|Nane))?\s*[:*+=;>\?\-\!\|/\\\s]+([^\n\r]+)',
            full_text,
            re.I
        )
        if rel_m:
            raw_rt = rel_m.group(1).lower()
            if raw_rt.startswith('f'):
                rel_type = 'Father'
            elif raw_rt.startswith('h'):
                rel_type = 'Husband'
            elif raw_rt.startswith('m'):
                rel_type = 'Mother'
            elif raw_rt.startswith('g'):
                rel_type = 'Guardian'
            else:
                rel_type = 'Other'
            rel_name = self.clean_name(rel_m.group(2))
            if not rel_name:
                # Check if relative name wrapped to the next line
                for idx_l, line in enumerate(lines):
                    if re.search(r'(Father|Fathar|Fether|Husband|Hushend|Hushand|Husban|Mother|Mothar|Mether|Other|Otners|Othars|Otliers|Guardian)', line, re.I):
                        if idx_l + 1 < len(lines):
                            nxt = lines[idx_l + 1]
                            if not re.search(r'\b(House|Howse|Age|Gender)\b', nxt, re.I):
                                rel_name = self.clean_name(nxt)
                        break

        # 4. Door / House Number
        door_no = ''
        house_m = re.search(
            r'(?:[HhlI1|]?[o0eau]us[ea]?|Howse|Hous|Inti|D\.?No|H\.?No)\s*(?:Number|Numbar|Num|No)?\s*[:*+=;>?\}\]\-\.\'\"it!|/\s]+([^\n\r]+)',
            full_text,
            re.I
        )
        if house_m:
            door_no = self.clean_door(house_m.group(1))

        # 5. Age (use word boundary and finditer from bottom-up so names like NAGESWARARAO never match 'Ag[e]')
        age = None
        ag_subs = {'O': '0', 'o': '0', 'Q': '0', 'D': '0', 'I': '1', 'l': '1', '|': '1', 'Z': '2', 'd': '4', '#': '4', 'A': '4', 'S': '5', 's': '5', 'G': '6', 'B': '8', '?': '7', '/': '7'}
        for age_m in reversed(list(re.finditer(r'(?:^|(?<=[\s\n\r0-9]))(?:[0-9]?Ag[e\?@aoc]|Age|Vayassu)\b\s*[:*+=;>?\-\.\'\"it|/\\!\}\]]{0,3}\s*(?:[1l]\s+)?([0-9OQoDBSlI|Z/\?d#A]{1,4})', full_text, re.I))):
            raw_ag = age_m.group(1).strip()
            # Guard 3 (Anti-False-Positive): Require at least 1 real digit (or classic 'Bd' -> 84) so words never become fake ages
            if not any(ch.isdigit() for ch in raw_ag) and raw_ag not in ('Bd', 'BO', 'B0'):
                continue
            if len(raw_ag) >= 3 and raw_ag[0] in ('?', '/'):
                raw_ag = raw_ag[1:]
            # Discard trailing OCR noise punctuation so '39?' or '21/' preserves genuine 2 digits
            if len(raw_ag) >= 3 and raw_ag[:2].isdigit() and raw_ag[-1] in ('?', '/', '-', '+', '!', '|'):
                raw_ag = raw_ag[:2]
            raw_ag = re.sub(r'(?<=\d)/(?=\d)', '', raw_ag)
            ag_digits = ''.join(ch if ch.isdigit() else ag_subs.get(ch, '') for ch in raw_ag)
            if ag_digits.isdigit():
                val = int(ag_digits)
                if val > 110 and len(ag_digits) == 3:
                    if ag_digits[0] in ('1', '7') and 18 <= int(ag_digits[1:]) <= 110:
                        val = int(ag_digits[1:])
                if 18 <= val <= 110:
                    age = val
                    break

        # 6. Gender
        gender = ''
        gender_m = re.search(
            r'(?:Gend[eao]r|Gencler|Ganclar|Gander|Lingamu|Gend)\s*[:*+=;>?\-\.\'\"it1l|/\\!\}\]\s]{0,6}(M[ao][l1i][eaos]|F[ea][mr]n?[aei][l1i][eaos]|Third|Transgender)',
            full_text,
            re.I
        )
        if gender_m:
            g_str = gender_m.group(1).lower()
            if 'f' in g_str:
                gender = 'Female'
            elif 'm' in g_str:
                gender = 'Male'
            elif 'third' in g_str or 'trans' in g_str:
                gender = 'Third Gender'
        else:
            if re.search(r'\b(F[ea][mr]n?[aei][l1i][eaos])\b', full_text, re.I):
                gender = 'Female'
            elif re.search(r'\b(M[ao][l1i][eaos])\b', full_text, re.I):
                gender = 'Male'

        # Infer Female if relationship is Husband and gender was unread
        if not gender and rel_type == 'Husband':
            gender = 'Female'

        return {
            'booth_sno': extracted_sno,
            'epic_no': extracted_epic or '',
            'voter_name': voter_name,
            'rel_type': rel_type,
            'rel_name': rel_name,
            'door_no': door_no,
            'age': age,
            'gender': gender,
            'raw_text': full_text
        }
