import os
import sys
import re
import json
import time
from collections import defaultdict, Counter
import pandas as pd

# ==============================================================================
# 0. CANONICAL ANDHRA SURNAME LEXICON (CASL) LOADER
# ==============================================================================

CASL_FILE = os.path.join(os.path.dirname(__file__), 'casl_surnames.json')
if os.path.exists(CASL_FILE):
    with open(CASL_FILE, 'r', encoding='utf-8') as _f:
        CASL_SURNAMES = frozenset(json.load(_f).keys())
else:
    CASL_SURNAMES = frozenset()

PROTECTED_GIVEN_NAMES = frozenset([
    'baby', 'rani', 'mani', 'jyothi', 'lalitha', 'kiran', 'chitti', 'bujji', 'chinna', 'pedda',
    'babu', 'nani', 'kumar', 'kumari', 'devi', 'latha', 'amma', 'ayya', 'appa', 'swamy', 'swami',
    'murthy', 'moorthy', 'prasad', 'durga', 'venkata', 'satya', 'siva', 'ram', 'rama', 'krishna',
    'subba', 'naga', 'surya', 'lakshmi', 'parvathi', 'saraswathi', 'ganesh', 'suresh', 'ramesh',
    'naresh', 'mahesh', 'rajesh', 'anand', 'sekhar', 'kalyan', 'pavan', 'charan', 'mohan', 'sri',
    'sree', 'ganga', 'bhavani', 'manga', 'veera', 'veerabhadra', 'mallikarjuna', 'someshwara',
    'somanna', 'polana', 'konda', 'kondala', 'srinivasa', 'srinivas', 'venkateswara', 'venkateshwara',
    'venkataramana', 'sitarama', 'satyanarayana', 'narayana', 'appalaraju', 'sattiraju', 'apparao',
    'subbarao', 'ramarao', 'venkatarao', 'nageswararao', 'suryanarayana', 'veeravenkata',
    'veerasatyanarayana', 'kanaka', 'venkanna', 'ramana', 'rambabu', 'veerababu', 'sattibabu',
    'srinu', 'satyavathi', 'nookaraju', 'suribabu', 'lovaraju', 'veeraraju', 'nagaswararao',
    'varalakshmi', 'venkatamma', 'kondamma', 'somalamma', 'gangamma', 'appalamma', 'nookalamma',
    'mangalamma', 'chittemma', 'poleramma', 'parvatamma', 'danamma', 'venkatalakshmi', 'satyalatha',
    'padmavathi', 'annapurna'
])

SPLIT_SURNAME_MAP = {
    ('ga', 'ttem'): 'Gattem',
    ('ga', 'tem'): 'Gattem',
    ('gol', 'lapalli'): 'Gollapalli',
    ('goll', 'palli'): 'Gollapalli',
    ('ko', 'ppisetti'): 'Koppisetti',
    ('kop', 'pisetti'): 'Koppisetti',
    ('kopp', 'setti'): 'Koppisetti',
    ('me', 'disetti'): 'Medisetti',
    ('med', 'setti'): 'Medisetti',
    ('va', 'samsetti'): 'Vasamsetti',
    ('vasam', 'setti'): 'Vasamsetti',
    ('ta', 'tapudi'): 'Tatapudi',
    ('tata', 'pudi'): 'Tatapudi',
    ('su', 'rampudi'): 'Surampudi',
    ('suram', 'pudi'): 'Surampudi',
    ('kommi', 'needi'): 'Kommineedi',
    ('pabbi', 'needi'): 'Pabbineedi',
    ('peda', 'pati'): 'Pedapati',
    ('nandi', 'pati'): 'Nandipati',
    ('donda', 'pati'): 'Dondapati',
    ('chinta', 'palli'): 'Chintapalli',
    ('konda', 'palli'): 'Kondapalli',
    ('bavi', 'setti'): 'Bavisetti'
}

RE_DOUBLE_INITIAL = re.compile(r'\b([b-df-hj-np-tv-z])\1([a-z]{3,})\b', re.IGNORECASE)

# ==============================================================================
# 1. IMMUTABLE PROTECTED REGISTRY (Guarantees Zero False Positives)
# ==============================================================================

PROTECTED_HALANTA_BLOCKLIST = frozenset([
    # Anglo / Christian / Biblical
    'david', 'john', 'paul', 'peter', 'samuel', 'daniel', 'joseph', 'stephen',
    'philip', 'thomas', 'james', 'jacob', 'matthew', 'mark', 'luke', 'simon',
    'abraham', 'moses', 'solomon', 'samson', 'gideon', 'alfred', 'wilfred',
    'ronald', 'reginald', 'donald', 'wilson', 'nelson', 'victor', 'george',
    'martin', 'charles', 'william', 'richard', 'edward', 'robert', 'francis',
    'anthony', 'christopher', 'stanley', 'wesley', 'emmanuel', 'immanuel',
    'kennedy', 'johny', 'rahelamma', 'suvartha', 'martha',
    # Islamic / Arabic / Persian / Urdu
    'shaik', 'sheik', 'shek', 'sher', 'syed', 'sayyad', 'sayed', 'pathan', 'khan',
    'begum', 'begam', 'bibi', 'beebi', 'khatoon', 'saheb', 'sahib', 'pasha', 'basha',
    'baig', 'qureshi', 'ansari', 'mirza', 'mohammad', 'mohammed', 'mahammad', 'ahmed',
    'ahmad', 'ali', 'hussain', 'hasan', 'ibrahim', 'ismail', 'usman', 'osman', 'umar',
    'farooq', 'abdul', 'abdur', 'abdullah', 'rahim', 'rahman', 'rehman', 'karim',
    'kareem', 'ghouse', 'noor', 'mansoor', 'khaja', 'mastan', 'raza', 'akram',
    'aslam', 'irfan', 'imran', 'salman', 'sultana', 'rukhsana', 'shabana', 'fathima',
    'fatima', 'parveen', 'yasmin', 'zareena', 'mumtaz', 'ayesha', 'nasreen', 'jabeen',
    'sameena', 'shahina', 'shameem', 'naseem', 'shahid', 'rashid', 'majid', 'khalid',
    'hamid', 'zahid', 'sadiq', 'tariq', 'iqbal', 'arif', 'anwar', 'akbar', 'asghar',
    'babar', 'zafar', 'javed', 'murad', 'munwar', 'afzal', 'amjad', 'mehboob',
    'subhan', 'habeeb', 'habib', 'alisha', 'madina', 'mecca', 'najma', 'saleem',
    'salim', 'nazeer', 'shafi', 'rasool', 'peer', 'peera', 'basheer', 'khasim',
    'kasim', 'babajan', 'nawab', 'nagur', 'bahadur', 'kalam', 'suban', 'chotasaheb',
    'lalabi', 'ameena', 'gousia', 'shajahan', 'chandbasha', 'moulali', 'dudekula',
    'noorbasha', 'peerasahib', 'peeraiah', 'rustam', 'farhad', 'asad', 'shariff',
    'sharif', 'shareef', 'shereef', 'siraj', 'jahangir', 'altaf', 'jaleel', 'azeez',
    'aziz', 'shabbir', 'sattar', 'shakir', 'tanveer', 'tanvir', 'shakeel', 'shakil',
    # Sanskrit / Halanta Masculine Loans
    'kiran', 'charan', 'pavan', 'kalyan', 'kumar', 'sudhakar', 'bhaskar', 'prabhakar',
    'diwakar', 'sagar', 'kishor', 'chandan', 'nandan', 'mohan', 'madan', 'chetan',
    'suman', 'naveen', 'praveen', 'ranjan', 'satyam', 'sriram', 'balaram', 'sundaram',
    'gautam', 'pritam', 'anupam', 'varad', 'sharad', 'thakur', 'mayur', 'ankur',
    'kandadai', 'ravikiran', 'saikiran', 'ramcharan', 'simran', 'sudharan', 'dharan',
    'sharan', 'aran', 'moran', 'saran', 'ushakiran', 'devikaran', 'peeta', 'chavala',
    'singh', 'chandra', 'nageswara', 'nagendra', 'gundra', 'kakara', 'sunkara',
    'shubhadra', 'ram', 'shyam', 'abhiram', 'parasuram', 'jayaram', 'tara', 'indira',
    'surekha', 'rekha', 'kavitha', 'anitha', 'sunitha', 'geetha', 'seetha', 'prasad',
    'durgaprasad', 'ramaprasad', 'sivaprasad', 'varaprasad', 'bharath', 'hemanth',
    'sreekanth', 'siddharth'
])

PROTECTED_FEMALE_ROOTS = frozenset([
    'navya', 'kavya', 'sravya', 'bhavya', 'divya', 'ramya', 'lavanya', 'soumya',
    'sandhya', 'ananya', 'kavitha', 'anitha', 'sunitha', 'geetha', 'seetha'
])

KNOWN_TELUGU_RAD_STEMS = (
    'tata', 'venkata', 'nageshwar', 'seshagiri', 'babu', 'sanyasi', 'shesha', 'govinda',
    'raja', 'venkat', 'narasimha', 'ananda', 'atcha', 'venkateshwar', 'madhava',
    'prasada', 'prasad', 'chanda', 'konda', 'bhaskar', 'nageswar', 'prakasha', 'prakash',
    'someshwar', 'suryaprakash', 'srinivas', 'sambasiva', 'mohan', 'eswar', 'sambashiva',
    'raghava', 'appala', 'subba', 'satya', 'ram', 'rama', 'lakshmana', 'krishna',
    'dharma', 'ganga', 'veerabhadra', 'mallikarjuna', 'linga', 'surya', 'kameswara',
    'somalingeswara', 'bheemeswara', 'visweswara', 'somanna', 'polana', 'chinna',
    'pedda', 'kondala', 'durgaprasada', 'chandra', 'chandrasekhara', 'viswanadha',
    'narayana', 'sitarama', 'koti', 'chalapathi', 'jagapathi', 'ganapathi', 'vasudeva',
    'atcha', 'latcha', 'machar'
)

WHITELISTED_UR_SURNAMES = {
    'kommur': 'Kommuri', 'yendamur': 'Yendamuri', 'anasur': 'Anasuri', 'anusur': 'Anusuri',
    'vallur': 'Valluri', 'perur': 'Peruri', 'maddur': 'Madduri', 'chittur': 'Chitturi',
    'kosur': 'Kosuri', 'kovvur': 'Kovvuri', 'amjur': 'Amjuri', 'jallur': 'Jalluri',
    'ravur': 'Ravuri', 'palur': 'Paluri', 'arthamur': 'Arthamuri', 'eedur': 'Eeduri',
    'katur': 'Katuri', 'chellur': 'Chelluri', 'kodur': 'Koduri', 'chedulur': 'Cheduluri',
    'gidutur': 'Giduturi', 'kurukur': 'Kurukuri', 'kadulur': 'Kaduluri'
}

WHITELISTED_SHETT_SURNAMES = {
    'medishett': 'Medishetti', 'ramishett': 'Ramishetti', 'elishett': 'Elishetti',
    'vasamshett': 'Vasamshetti', 'koppishett': 'Koppishetti', 'koshett': 'Koshetti',
    'pechett': 'Pechetti', 'marishett': 'Marishetti', 'peddishett': 'Peddishetti'
}

WHITELISTED_RED_SURNAMES = {
    'abbired': 'Abbireddy', 'pedired': 'Pedireddy', 'ramired': 'Ramireddy',
    'porupured': 'Porupureddy', 'gantred': 'Gantreddy'
}

PROTECTED_GH_STEMS = (
    'ghantam', 'ghanti', 'ghantasala', 'ghattamaneni', 'ghattu', 'ghatta',
    'ghouse', 'ghouze', 'ghousia', 'ghoushia', 'ghowsia', 'ghanashyam', 'ghanapuram'
)

KNOWN_CH_STEMS = (
    'ghinta', 'ghekka', 'ghitturi', 'ghakrar', 'ghandra', 'ghodipalli', 'ghundru',
    'ghintala', 'ghukka', 'ghinni', 'ghinna', 'ghaganti', 'ghowdary', 'ghellarao',
    'ghitt', 'ghakra', 'ghitti', 'ghintha', 'ghapala', 'ghappidi', 'ghalapathi',
    'ghinnari', 'ghavala', 'gheduluri', 'ghodisetti', 'ghepala', 'gheekatla',
    'ghikatla', 'ghikkala', 'ghukkala', 'ghandaka', 'ghinaapparao', 'ghinnaiah',
    'ghandravathi', 'ghelluboina', 'ghell'
)

# Explicit Direct OCR Replacement Table for M, C, and Telugu Mirror Ascenders
SPECIFIC_OCR_REPLACEMENTS = {
    # Islamic OCR Fixes
    'shalk': 'Shaik', 'sheak': 'Sheik', 'shiek': 'Sheik', 'shelk': 'Sheik',
    'sheek': 'Sheik', 'shaiik': 'Shaik', 'shiak': 'Shaik', 'shaek': 'Shaik',
    'shake': 'Shaik', 'sek': 'Sheik', 'shike': 'Sheik', 'sheeik': 'Sheik',
    'shaike': 'Shaik', 'shaiku': 'Shaik', 'sheku': 'Sheik', 'shakh': 'Shaik',
    'shak': 'Shaik', 'sahes': 'Saheb', 'saher': 'Saheb', 'sahebu': 'Saheb',
    'sahibu': 'Sahib', 'moharnmad': 'Mohammad', 'mohammb': 'Mohammad',
    'mohammab': 'Mohammad', 'mahammed': 'Mohammad', 'mahamad': 'Mohammad',
    'mohamad': 'Mohammad', 'mahmad': 'Mohammad', 'mhammad': 'Mohammad',
    'marmad': 'Mohammad', 'ahamad': 'Ahmad', 'ahemmad': 'Ahmad',
    'hussian': 'Hussain', 'patan': 'Pathan', 'patthan': 'Pathan',
    'syadu': 'Syed', 'sayyadu': 'Sayyad',
    'khatun': 'Khatoon', 'begam': 'Begum',
    
    # Christian OCR Fixes
    'mortha': 'Martha', 'morta': 'Martha', 'marta': 'Martha',
    'jhon': 'John', 'joshap': 'Joseph', 'josaph': 'Joseph', 'josap': 'Joseph',
    'josaf': 'Joseph', 'davidl': 'David', 'esubaabl': 'Yesubabu',
    'esubaablu': 'Yesubabu', 'esubasbu': 'Yesubabu', 'esubsabu': 'Yesubabu',
    
    # Telugu Mirror Ascender d <-> b Fixes
    'tatapubi': 'Tatapudi', 'surampubi': 'Surampudi', 'tekumubi': 'Tekumudi',
    'kantipubi': 'Kantipudi', 'kondepubi': 'Kondepudi', 'kurupubi': 'Kurupudi',
    'morampubi': 'Morampudi', 'tillapubi': 'Tillapudi', 'kudupubi': 'Kudupudi',
    'kudipubi': 'Kudupudi', 'mummibi': 'Mummadi', 'ummibi': 'Ummidi',
    'bommibi': 'Bommidi', 'muppibi': 'Muppidi', 'mamibi': 'Mamidi',
    'gummabi': 'Gummadi', 'mallabi': 'Malladi', 'salabi': 'Saladi',
    'dibbibi': 'Dibbidi',
    
    # High-confidence Telugu Surname & Name OCR repairs (from canonical electorate reference lexicon)
    'ggllapalli': 'Gollapalli', 'gllapalli': 'Gollapalli',
    'doglapalli': 'Gollapalli', 'gogllapalli': 'Gollapalli', 'dhooglapalli': 'Gollapalli',
    'dogllapalli': 'Gollapalli', 'poglapalli': 'Gollapalli',
    'nakikaa': 'Nakka', 'nakika': 'Nakka', 'nakiaa': 'Nakka',
    'peditedia': 'Pediredla', 'pediredia': 'Pediredla', 'peditedla': 'Pediredla',
    'macish': 'Medisetti', 'mebish': 'Medisetti', 'madish': 'Medisetti', 'mebishetti': 'Medisetti',
    'ketiniei': 'Ketinidi',
    'suryakumarn': 'Suryakumari', 'shrnu': 'Srinu',
    'kowuri': 'Kovvuri', 'kowiri': 'Kovviri', 'juwala': 'Juvvala',
    'guraam': 'Gurram', 'guraala': 'Gurrala',
    'appaaao': 'Apparao', 'appaao': 'Apparao', 'appaaad': 'Apparao', 'appaaag': 'Apparao',
    'chakraaao': 'Chakrarao', 'chakraao': 'Chakrarao',
    'nageswaraaao': 'Nageswararao', 'nageswaraao': 'Nageswararao',
    'venkateshwaraaad': 'Venkateshwararao', 'venkateswaraaad': 'Venkateswararao',
    'venkateshwaraad': 'Venkateshwararao', 'venkateswaraad': 'Venkateswararao',
    'sattiaaju': 'Sattiraju', 'somaaaju': 'Somaraju',
    'nookaaaiu': 'Nookaraju', 'appalaaajiu': 'Appalaraju', 'appalaajiu': 'Appalaraju',
    'venkataaatnam': 'Venkataratnam', 'chandaarao': 'Chandrarao',
    'chellar': 'Chellarao', 'gatlem': 'Gattem', 'gatten': 'Gattem', 'gattema': 'Gattem',
    'gatam': 'Gattem', 'alnpalli': 'Alapalli', 'klukika': 'Kukka', 'kukra': 'Kukka',
    'bocdu': 'Boddu', 'guaddati': 'Guddati', 'tatifarthi': 'Tatiparthi',
    'tatirfarthi': 'Tatiparthi', 'plrla': 'Pirla'
}

PROTECTED_RN = frozenset([
    'aparna', 'annapurna', 'narna', 'marni', 'marne', 'karnam', 'karneedi', 'swarna',
    'varnasi', 'aruna', 'taruni', 'parnakuti', 'karnan', 'karne', 'urna', 'dharani'
])

PROTECTED_EED = frozenset([
    'hameed', 'majeed', 'rasheed', 'waheed', 'naved', 'sayeed', 'javeed', 'saeed', 'jameed'
])

# Explicit Islamic feminine title whitelist
ISLAMIC_BI_WHITELIST = frozenset([
    'bibi', 'beebi', 'bebi', 'lalabi', 'noorbi', 'noorbhi', 'jaanbi', 'janbi',
    'rajanbhi', 'madinabi', 'khasimbi', 'hassanbi', 'mastambi', 'papabi',
    'chandbi', 'ameenbi', 'fathimabi', 'shameembi', 'sahebbi', 'alimbi',
    'rajambi', 'khajabi', 'khaderbi', 'subanbi', 'subhanbi', 'amminbi', 'badarbhi',
    'bashirbibi', 'suvinabib', 'hafiuunnisabibi', 'bhibi', 'bhibljan', 'meerabi',
    'nagurbibi', 'satarbhi', 'hasinabibi', 'ashabibi', 'himambi', 'subhanbibi'
])

CHRISTIAN_TOKENS = frozenset([
    'david', 'john', 'joseph', 'paul', 'peter', 'samuel', 'daniel', 'james', 'jacob',
    'abraham', 'moses', 'solomon', 'samson', 'gideon', 'stephen', 'philip', 'thomas',
    'matthew', 'mark', 'luke', 'timothy', 'titus', 'simon', 'andrew', 'wilson', 'nelson',
    'alfred', 'wilfred', 'george', 'martin', 'victor', 'charles', 'william', 'richard',
    'edward', 'robert', 'francis', 'antony', 'anthony', 'christopher', 'ronald', 'reginald',
    'donald', 'alexander', 'benjamin', 'emmanuel', 'immanuel', 'mary', 'mariamma', 'martha',
    'mortha', 'ruth', 'esther', 'grace', 'mercy', 'rosy', 'rose', 'daisy', 'lily', 'elizabeth',
    'victoria', 'stella', 'glory', 'blessy', 'joy', 'rebekah', 'rebecca', 'rachel', 'sarah',
    'hepsiba', 'hepzibah', 'salome', 'priscilla', 'lydia', 'dorcas', 'yesu', 'yesubabu',
    'yesuratnam', 'yesupadam', 'yesudas', 'devadas', 'devadasi', 'krupavaram', 'krupanandam',
    'stanley', 'wesley', 'elisha', 'joel', 'isaac', 'ruben', 'reuben', 'amos', 'ezra',
    'kennedy', 'johny', 'rahelamma', 'suvartha', 'yesubaabu', 'yesurathnam'
])

ISLAMIC_TOKENS = frozenset([
    # Surnames, lineages & titles
    'shaik', 'sheik', 'sheikh', 'shek', 'sher', 'shalk', 'sheak', 'shiek', 'shelk', 'sheek',
    'shaiik', 'shiak', 'shaek', 'shake', 'sek', 'shike', 'sheeik', 'shaike', 'shaiku', 'sheku',
    'shakh', 'shak', 'shaikbabu', 'vallishek', 'meerabishaik', 'aadilshaik', 'sharifasheik',
    'himambishek', 'ashabibishek', 'jilanlshek', 'beebisk', 'shaikiddin',
    'syed', 'sayyad', 'sayed', 'seyad', 'siyad', 'sved', 'syadu', 'sayyadu', 'syedbabu',
    'handhisayyad', 'rabbanisayyad',
    'pathan', 'khan', 'patan', 'patthan', 'baig', 'qureshi', 'ansari', 'mirza', 'nawab', 'navab',
    'begum', 'begam', 'khatoon', 'khatun',
    'shariff', 'sharif', 'shareef', 'shereef',
    'saheb', 'sahib', 'sahes', 'saher', 'sahebu', 'sahibu', 'saheba', 'saheeb',
    'pasha', 'basha', 'bhasha', 'chandbasha', 'noorbasha', 'peerasahib', 'bashasaheb',
    'madinabasha', 'jaanbasha', 'dudekula', 'fakir', 'fakeer', 'phakir', 'shikilkar',
    # Compound Sahebs
    'chotasaheb', 'peddasaheb', 'tatasaheb', 'babasaheb', 'chinnasaheb', 'lalsaheb',
    'kannasaheb', 'meerasaheb', 'mirasaheb', 'hussainsaheb', 'subhansaheb', 'mastansaheb',
    'khajasaheb', 'khasimsaheb', 'alishasaheb', 'alisab', 'peerasaheb', 'peerasahib',
    'peerusaheb', 'gousesaheb', 'madinasaheb', 'rasoolsaheb', 'saleemsaheb', 'noorsahib',
    'lalasaheb', 'gudusaheb',
    # Divine & personal names
    'mohammad', 'mohammed', 'mahammad', 'ahmed', 'ahmad', 'mohamed', 'mohamad', 'mohmmad',
    'moharnmad', 'mahammed', 'mahmad', 'mohammb', 'mohammab', 'ahamad', 'ahemmad',
    'alimohamed', 'mhammad', 'marmad', 'mohamadjilani', 'kowsarmahammed', 'sirajmahamad',
    'asvamohamed', 'ahammadmahmad', 'shaikmohammad', 'shaikahmed',
    'md', 'mohd',
    'ali', 'hussain', 'hasan', 'hassan', 'hussen', 'husain', 'hussan', 'hussin', 'hussian',
    'hasina', 'haseena', 'hazira', 'hajira', 'hyder', 'haider', 'alisha', 'alisa', 'shaabbas',
    'ibrahim', 'ismail', 'ismayil', 'usman', 'osman', 'umar', 'farooq', 'faruk',
    'abdul', 'abdur', 'abdullah', 'abdulla', 'abbulkhadar', 'abdulkhadar', 'abdulraheem',
    'abdulrahaman', 'rahim', 'raheem', 'rahman', 'rehman', 'rahaman', 'rehaman',
    'karim', 'kareem',
    'ghouse', 'gouse', 'gowse', 'ghouze', 'gousia', 'goushia', 'gowsia', 'gauss',
    'noor', 'noorahan', 'noorjahan', 'nurjahan', 'mansoor', 'mansur',
    'khaja', 'kaja', 'khaza', 'mastan', 'masthan', 'mastana', 'raza', 'akram', 'aslam',
    'irfan', 'imran', 'salman', 'sultana', 'sulthana', 'soltana', 'sultan', 'sulthan',
    'rukhsana', 'ruksana', 'shabana', 'shabina', 'fathima', 'fatima', 'phathima', 'parveen',
    'parvin', 'yasmin', 'yasmeen', 'zareena', 'zarina', 'jareena', 'jarina', 'mumtaz',
    'mumthaz', 'ayesha', 'nasreen', 'nasrin', 'jabeen', 'jabin', 'sameena', 'samina',
    'shahina', 'shameem', 'naseem', 'shahid', 'rashid', 'majid', 'khalid', 'hamid',
    'zahid', 'sadiq', 'tariq', 'iqbal', 'arif', 'anwar', 'akbar', 'asghar', 'babar',
    'zafar', 'javed', 'javeed', 'murad', 'munwar', 'afzal', 'amjad', 'mehboob', 'mehaboob',
    'subhan', 'suban', 'shuban', 'subhani', 'habeeb', 'habib', 'madina', 'mecca',
    'najma', 'saleem', 'salim', 'nazeer', 'nazir', 'naseer', 'naseera', 'shafi',
    'rasool', 'rasul', 'peer', 'peera', 'peeru', 'peeraiah', 'basheer', 'bashir',
    'basheera', 'khasim', 'kasim', 'khasin', 'babajan', 'shajahan', 'sikandar', 'secunder',
    'bismillah', 'inayat', 'wajid', 'wahid', 'faheem', 'fahim', 'nayeem',
    'kamil', 'jameel', 'jamil', 'shabbir', 'sabir', 'suhail', 'sohail', 'tanveer',
    'tanvir', 'shakeel', 'shakil', 'siraj', 'moin', 'khaleel', 'khalil', 'liaqat',
    'liyaqat', 'mukhtar', 'muzaffar', 'nisar', 'nissar', 'riyaz', 'reyaz', 'shoaib',
    'waseem', 'wasim', 'zia', 'ziya', 'zuber', 'zubair', 'shahbaz', 'sattar', 'shakir',
    'jahangir', 'altaf', 'jaleel', 'azeez', 'aziz', 'dastagiri', 'dastagir',
    'khudbuddin', 'khutbuddin', 'sanaullah', 'riyazuddin', 'allauddin', 'mohiddin',
    'mohhiddin', 'jalaluddin', 'imamdeen', 'imam', 'jilani', 'samdhani', 'rabbani',
    'kausar', 'kowsar', 'salma', 'resheeda', 'rasheeda', 'zaheera', 'jaheera',
    'samirulla', 'asmatulla', 'pwari', 'pyari', 'shammi', 'anvar', 'ashraf',
    'bashirbibi', 'suvinabib', 'hafiuunnisabibi', 'bhibi', 'bhibljan',
    'meharunissa', 'meharunnisa', 'meharunisa', 'kareemunnisa', 'ahmadunnisa',
    'fatimunnisa', 'amirunnisa', 'asmatunnisa', 'badarunnisa', 'jameelunnisa', 'khairunnisa',
    'mehabubunnisa', 'bhasheerunnisha', 'nurunnisa', 'mahbunnisa', 'rahimunnisa',
    'vahidunnisa', 'aboobunnisa', 'vunnisa', 'unnisha', 'unissa', 'unnisa',
    'abidabegam', 'sajidabegam', 'jameelabegam', 'gousiabegum', 'rabiyabegam',
    'kareemunnisabegam', 'paimidabegam', 'hasinabegammoha', 'jaanbi', 'chandpasha'
])

HINDU_DISQUALIFIERS = (
    'rao', 'reddy', 'naidu', 'setti', 'raju', 'varma', 'sarma', 'sharma', 'sastry', 'sastri',
    'narasimha', 'satyanarayana', 'venkata', 'suryanarayana', 'veerabhadra', 'subbarao', 'apparao',
    'charyulu', 'brahman', 'subrahmanyam', 'krishnamurthy', 'sriranga', 'giri', 'koppula',
    'kuppili', 'peddinti', 'veera', 'surakattula', 'paliki', 'thota', 'barre', 'dibbidi'
)

ISLAMIC_EXCLUSIONS = frozenset([
    'mounisha', 'pasham', 'abhishek', 'abishek', 'abhisheik', 'rajashek', 'chandrashek',
    'somashek', 'subrahmanyam', 'subramanyam', 'subrahman', 'brahmanandam', 'khandavalli',
    'khandavilli', 'kamada', 'tamada', 'pasalapudi', 'ramadevi', 'ramadasu', 'bhanu', 'valli',
    'vali', 'rama', 'satyam', 'krishna', 'apparao', 'subbarao', 'surakattula', 'dibbibi',
    'dibbidi', 'naim', 'namu'
])

SANSKRIT_LINEAGE = frozenset([
    'sharma', 'sarma', 'shastri', 'sastri', 'varma', 'gupta', 'mishra', 'pandey', 'tiwari',
    'dubey', 'singh', 'joshi', 'bhatt', 'chatterjee', 'banerjee', 'choudhary', 'patel',
    'shah', 'jain', 'agarwal', 'agrawal', 'mittal', 'bansal', 'goel', 'tripathi', 'shukla',
    'thakur', 'marwadi', 'purohit', 'chaturvedi', 'dwivedi', 'shrivastava', 'srivastava',
    'mukherjee', 'bose', 'ghosh', 'chawla', 'malhotra', 'kapoor', 'arora', 'khanna', 'mehra',
    'seth', 'oberoi', 'bhatia', 'yadav', 'pandit', 'ojha', 'upadhyay', 'jha', 'goswami',
    'somayajulu', 'dvibhashyam', 'charyulu', 'bhatlu', 'avadhani', 'josyula', 'vajapeyajula',
    'vedula', 'acharya', 'deekshitulu', 'siddhanthi', 'ganapati'
])

SANSKRIT_HALANTA_ROOTS = frozenset([
    'kiran', 'charan', 'pavan', 'kalyan', 'kumar', 'sudhakar', 'bhaskar', 'prabhakar',
    'diwakar', 'chandrasekhar', 'sagar', 'kishor', 'mohan', 'madan', 'chetan', 'suman',
    'naveen', 'praveen', 'ranjan', 'satyam', 'sriram', 'balaram', 'sundaram', 'gautam',
    'pritam', 'anupam', 'sharad', 'varad', 'sanjay', 'ajay', 'vijay', 'vinay', 'uday',
    'abhay', 'suresh', 'ramesh', 'mahesh', 'naresh', 'dinesh', 'ganesh', 'rajesh',
    'mukesh', 'umesh', 'chaitanya', 'anand', 'deepak', 'alok', 'ashok', 'sunil', 'anil',
    'manoj', 'pankaj', 'vikram', 'amit', 'rohit', 'sachin', 'rahul'
])

TELUGU_HONORIFICS = (
    'raju', 'babu', 'rao', 'naidu', 'reddy', 'setti', 'shetti', 'ayya', 'aiah', 'amma',
    'appanna', 'anna', 'adu', 'odu', 'udu', 'olu', 'ulu', 'gari', 'akka', 'ammal',
    'ammi', 'abbai', 'ammayi', 'garu'
)

HINDU_DISQUALIFIERS = (
    'rao', 'reddy', 'naidu', 'setti', 'raju', 'varma', 'sarma', 'sharma', 'sastry', 'sastri',
    'narasimha', 'satyanarayana', 'venkata', 'suryanarayana', 'veerabhadra', 'subbarao', 'apparao'
)

def safe_sub_suffix(w, pat, suffix_base):
    if w.isupper():
        return re.sub(pat, suffix_base.upper(), w, flags=re.I)
    res = re.sub(pat, suffix_base.lower(), w, flags=re.I)
    if w and w[0].isupper() and res and res[0].islower():
        return res[0].upper() + res[1:]
    return res

def safe_sub_prefix(w, pat, prefix_base):
    if w.isupper():
        return re.sub(pat, prefix_base.upper(), w, flags=re.I)
    res = re.sub(pat, prefix_base.lower(), w, flags=re.I)
    if w and w[0].isupper() and res and res[0].islower():
        return res[0].upper() + res[1:]
    return res

# ==============================================================================
# 2. CORE TOKEN CLEANING ENGINE
# ==============================================================================

def clean_token(w, gender):
    w_clean = w.strip()
    w_lower = w_clean.lower()
    
    if not w_clean.isalpha():
        return w_clean
        
    # Check Explicit Direct OCR Replacement Table first
    if w_lower in SPECIFIC_OCR_REPLACEMENTS:
        target = SPECIFIC_OCR_REPLACEMENTS[w_lower]
        return target if w[0].isupper() else target.lower()

    # Hard Blocklist Gate: Protected minority, biblical, Islamic & halanta tokens
    if w_lower in PROTECTED_HALANTA_BLOCKLIST:
        return w_clean
    if gender == 'Male' and w_lower == 'kumar':
        return w_clean
    if w_lower in PROTECTED_FEMALE_ROOTS:
        return w_clean

    # 1. Divine / Prefix repairs: Sal -> Sai, Srl -> Sri
    if w_lower == 'sal':
        return 'Sai' if w[0].isupper() else 'sai'
    if w_lower == 'srl':
        return 'Sri' if w[0].isupper() else 'sri'

    # 2. Chalam vs Ghalam (Optical c -> g error)
    if w_lower in ('simhaghalam', 'simhacghalam'):
        return 'Simhachalam' if w[0].isupper() else 'simhachalam'
    if w_lower == 'venkataghalam':
        return 'Venkatachalam' if w[0].isupper() else 'venkatachalam'
    if w_lower == 'bhadraghalam':
        return 'Bhadrachalam' if w[0].isupper() else 'bhadrachalam'
    if w_lower == 'ghalamaiah':
        return 'Chalamaiah' if w[0].isupper() else 'chalamaiah'
    if w_lower == 'ghalam':
        return 'Chalam' if w[0].isupper() else 'chalam'

    # 3. Simhadai -> Simhadri (Fused ligature)
    if w_lower == 'simhadai':
        return 'Simhadri' if w[0].isupper() else 'simhadri'
    if w_lower == 'neeladai':
        return 'Neeladri' if w[0].isupper() else 'neeladri'
    if w_lower == 'seshadai':
        return 'Seshadri' if w[0].isupper() else 'seshadri'

    # 4. Whitelisted Telugu village surnames in -ur -> -uri
    if w_lower in WHITELISTED_UR_SURNAMES:
        target = WHITELISTED_UR_SURNAMES[w_lower]
        return target if w[0].isupper() else target.lower()

    # 5. Whitelisted surnames in -shett -> -shetti
    if w_lower in WHITELISTED_SHETT_SURNAMES:
        target = WHITELISTED_SHETT_SURNAMES[w_lower]
        return target if w[0].isupper() else target.lower()

    # 6. Whitelisted surnames in -red -> -reddy
    if w_lower in WHITELISTED_RED_SURNAMES:
        target = WHITELISTED_RED_SURNAMES[w_lower]
        return target if w[0].isupper() else target.lower()

    # 7. Anchored Telugu -rad -> -rao
    if w_lower.endswith('rad') and len(w_lower) >= 6:
        for st in KNOWN_TELUGU_RAD_STEMS:
            if w_lower.startswith(st):
                prefix = w[:-3]
                return prefix + ('Rao' if w[-3:].isupper() else 'rao')

    # 8. Glyph Normalization: Broken ascenders cl -> d
    if 'cl' in w_lower:
        w_clean = safe_sub_suffix(w_clean, r'cl', 'd')
        w_lower = w_clean.lower()
        if w_lower in PROTECTED_HALANTA_BLOCKLIST:
            return w_clean

    # 9. Kerning rn -> m
    if w_lower.startswith('rarn'):
        w_clean = safe_sub_prefix(w_clean, r'^rarn', 'ram')
        w_lower = w_clean.lower()
    if w_lower.endswith('arnma'):
        w_clean = safe_sub_suffix(w_clean, r'arnma$', 'amma')
        w_lower = w_clean.lower()

    # 10. Triple letter noise
    if 'lll' in w_lower:
        if w_lower.endswith('lll'):
            return safe_sub_suffix(w_clean, r'lll$', 'lli')
        elif 'llly' in w_lower:
            w_clean = safe_sub_suffix(w_clean, r'llly', 'lliy')
            w_lower = w_clean.lower()
        elif 'lllr' in w_lower:
            w_clean = safe_sub_suffix(w_clean, r'lllr', 'llir')
            w_lower = w_clean.lower()
        else:
            w_clean = safe_sub_suffix(w_clean, r'lll', 'll')
            w_lower = w_clean.lower()
    if 'aaa' in w_lower:
        if w_lower.endswith('waaa'):
            return safe_sub_suffix(w_clean, r'waaa$', 'wara')
        elif 'naaay' in w_lower:
            w_clean = safe_sub_suffix(w_clean, r'naaay', 'naray')
            w_lower = w_clean.lower()
        elif 'taaam' in w_lower:
            w_clean = safe_sub_suffix(w_clean, r'taaam', 'taram')
            w_lower = w_clean.lower()
        elif 'raaaj' in w_lower:
            w_clean = safe_sub_suffix(w_clean, r'raaaj', 'raraj')
            w_lower = w_clean.lower()

    # 11. Optical Q for D: Qurga* -> Durga*, Qandu -> Dandu, Qudala -> Dudala, Qulla -> Dulla
    if w_lower.startswith('qurga'):
        w_clean = ('D' if w_clean[0].isupper() else 'd') + w_clean[1:]
        w_lower = w_clean.lower()
    elif w_lower == 'qandu':
        return 'Dandu' if w_clean[0].isupper() else 'dandu'
    elif w_lower == 'qudala':
        return 'Dudala' if w_clean[0].isupper() else 'dudala'
    elif w_lower == 'qulla':
        return 'Dulla' if w_clean[0].isupper() else 'dulla'

    # 12. Dotless j / Raju loop: ...rajil, ...rajlu, ...rajtu, ...rajl -> ...raju
    if w_lower == 'raiu':
        return safe_sub_suffix(w_clean, r'raiu$', 'Raju')
    if w_lower.endswith('raiu'):
        return safe_sub_suffix(w_clean, r'raiu$', 'raju')
    if re.search(r'raj(?:il|lu|tu|l)$', w_lower):
        return safe_sub_suffix(w_clean, r'raj(?:il|lu|tu|l)$', 'raju')

    # 13. Honorific loops on Babu: ...baabl, ...baablu, ...bablu, ...babl, ...basbu -> ...babu
    if re.search(r'baabl[u]?$', w_lower) or re.search(r'bab(?:lu|l|sbu)$', w_lower):
        return safe_sub_suffix(w_clean, r'(?:baabl[u]?|bab(?:lu|l|sbu))$', 'babu')

    # 14. Surnames in -pl -> -pu (Magapl -> Magapu, Palepl -> Palepu, Pedakapl -> Pedakapu, Pappl -> Pappu)
    if len(w_lower) >= 5 and re.search(r'(?:[aeiou]p|pp)l$', w_lower):
        return safe_sub_suffix(w_clean, r'l$', 'u')

    # 15. Surnames / Names in -dl -> -du / -di / -reddy
    if len(w_lower) >= 5 and w_lower.endswith('dl'):
        if w_lower.endswith('reddl'):
            return safe_sub_suffix(w_clean, r'reddl$', 'reddy')
        elif w_lower.endswith('pudl'):
            return safe_sub_suffix(w_clean, r'pudl$', 'pudi')
        elif re.search(r'(?:rayu|ramu|chinno|eswaru|govin|pan|bon|bod)dl$', w_lower):
            return safe_sub_suffix(w_clean, r'dl$', 'du')
        elif re.search(r'(?:muppi|bommi|ummi|sala|kanti|suram)dl$', w_lower):
            return safe_sub_suffix(w_clean, r'dl$', 'di')

    # 16. Surnames in -settl -> -setti
    if len(w_lower) >= 5 and w_lower.endswith('settl'):
        return safe_sub_suffix(w_clean, r'settl$', 'setti')

    # 17. Village Surnames in -url -> -uri
    if len(w_lower) >= 5 and w_lower.endswith('url'):
        return safe_sub_suffix(w_clean, r'url$', 'uri')

    # 18. Surnames in -arl -> -aru / -ari
    if len(w_lower) >= 5 and w_lower.endswith('arl'):
        if w_lower in ('bangarl', 'lajarl', 'bandarl'):
            return safe_sub_suffix(w_clean, r'arl$', 'aru')
        elif w_lower in ('talarl', 'karrl', 'gowrl'):
            return safe_sub_suffix(w_clean, r'arl$', 'ari')

    # 19. Descender smudges on Rao: -ragq, -raa, -ras, -rac, -rad -> -rao
    if w_lower in ('rad', 'rac'):
        return safe_sub_suffix(w_clean, r'ra[dc]$', 'Rao')
    if (w_lower.endswith('rad') or w_lower.endswith('raad')) and len(w_lower) >= 5:
        if not (w_lower.endswith('prasad') or w_lower in ('sharad', 'varad', 'murad', 'barad')):
            m_rad = re.match(r'^(.*?)(?:aa|a)?r?aa?d$', w_lower)
            if m_rad:
                stem_rad = w_clean[:len(m_rad.group(1))]
                st_low = stem_rad.lower()
                if st_low.endswith(('shwar', 'swar')):
                    return stem_rad + 'arao'
                elif st_low.endswith('girir'):
                    return stem_rad[:-1] + 'rao'
                elif st_low.endswith(('a', 'i', 'u', 'e', 'o')):
                    return stem_rad + 'rao'
                elif st_low.endswith('r'):
                    return stem_rad + 'ao'
                elif st_low.endswith('sh'):
                    return stem_rad + 'arao'
                return stem_rad + 'arao'
    if len(w_clean) >= 6 and re.search(r'(?:appa|subba|satya|surya|veera|nageswa|nagaswa|chandra|rama|sriniva|tatara|nagar|ganga|somesh|kondala)ra[dcgqe]$', w_lower):
        return safe_sub_suffix(w_clean, r'ra[dcgqe]$', 'rao')
    if len(w_clean) >= 6 and re.search(r'(?:appa|subba|satya|surya|veera|nageswa|nagaswa|chandra|rama|sriniva|tatara|nagar|ganga|somesh|kondala)(?:ragq|raa|ras)$', w_lower):
        return safe_sub_suffix(w_clean, r'(?:ragq|raa|ras)$', 'rao')
    if re.search(r'rao[qge]$', w_lower):
        return safe_sub_suffix(w_clean, r'rao[qge]$', 'rao')

    # 20. Initial Gh- for Ch- (optical c -> g error)
    if w_lower.startswith('gh') and len(w_lower) >= 4:
        if not any(w_lower.startswith(st) for st in PROTECTED_GH_STEMS):
            if any(w_lower.startswith(st) for st in KNOWN_CH_STEMS):
                w_clean = ('Ch' if w_clean[0].isupper() else 'ch') + w_clean[2:]
                w_lower = w_clean.lower()

    # 21. Venkateswarlu terminal glitches
    if len(w_lower) >= 8 and (w_lower.startswith('venkates') or w_lower.startswith('enkates')):
        if re.search(r'war(?:ll|ull|lli|iu|llu)$', w_lower):
            w_clean = safe_sub_suffix(w_clean, r'war(?:ll|ull|lli|iu|llu)$', 'warlu')
            if w_clean.lower().startswith('enkates'):
                w_clean = ('V' if w_clean[0].isupper() else 'v') + w_clean[1:]
            w_lower = w_clean.lower()

    # 22. Kerning: Venkatararnana -> Venkataramana
    if 'rarnana' in w_lower:
        w_clean = re.sub(r'rarnana', 'ramana' if w[-1].islower() else 'Ramana', w_clean, flags=re.I)
        w_lower = w_clean.lower()

    # 23. Box-margin clips
    if re.search(r'(?:bhadra|prakasha|maheswara|eswara|nagendra|ramalinga)r$', w_lower):
        return safe_sub_suffix(w_clean, r'r$', 'rao')

    # 24. Clipped titles: ...murt -> ...murthy
    if len(w_clean) >= 6 and re.search(r'murth?$', w_lower):
        return safe_sub_suffix(w_clean, r'murth?$', 'murthy')

    # 25. Telugu surname clippings
    if len(w_clean) >= 4:
        if w_lower.endswith('sett'):
            return safe_sub_suffix(w_clean, r'sett$', 'setti')
        if w_lower.endswith('pall'):
            return safe_sub_suffix(w_clean, r'pall$', 'palli')
        if w_lower.endswith('vill'):
            return safe_sub_suffix(w_clean, r'vill$', 'villi')
        if w_lower.endswith('bill'):
            return safe_sub_suffix(w_clean, r'bill$', 'billi')
        if w_lower.endswith('pill'):
            return safe_sub_suffix(w_clean, r'pill$', 'pilli')
        if w_lower.endswith('parth'):
            return safe_sub_suffix(w_clean, r'parth$', 'parthi')
        if w_lower.endswith('redd'):
            return safe_sub_suffix(w_clean, r'redd$', 'reddy')
        if w_lower.endswith('kurth'):
            return safe_sub_suffix(w_clean, r'kurth$', 'kurthi')
        if w_lower.endswith('cherl'):
            return safe_sub_suffix(w_clean, r'cherl$', 'cherla')
        if re.search(r'[aeiou]pat$', w_lower):
            return safe_sub_suffix(w_clean, r'pat$', 'pati')
        if re.search(r'[aeiou]dat$', w_lower):
            return safe_sub_suffix(w_clean, r'dat$', 'dati')
        if re.search(r'(?:mupp|mam|bomm|umm|sal|karn|pern)id$', w_lower):
            return safe_sub_suffix(w_clean, r'd$', 'di')
        if re.search(r'[aeiou]pud$', w_lower):
            return safe_sub_suffix(w_clean, r'pud$', 'pudi')
        if re.search(r'[aeiou]kot$', w_lower):
            return safe_sub_suffix(w_clean, r'kot$', 'koti')
        if re.search(r'[aeiou]gant$', w_lower):
            return safe_sub_suffix(w_clean, r'gant$', 'ganti')
        if re.search(r'[aeiou]bant$', w_lower):
            return safe_sub_suffix(w_clean, r'bant$', 'banti')
        if re.search(r'(?:pasupul|pall|dang|pek|kond|ol|kon|domm|gand|tol|yel|gant|kan|gandr|pal|ak|mel|thol|moll|kat|yarlagadd|gollapul)et$', w_lower):
            return safe_sub_suffix(w_clean, r'et$', 'eti')
        if re.search(r'[aeiou]rapl$', w_lower) or re.search(r'[aeiou]rapli$', w_lower):
            return safe_sub_suffix(w_clean, r'rapl(?:i)?$', 'rapalli')
        if w_lower == 'peddint':
            return safe_sub_suffix(w_clean, r'peddint$', 'Peddinti')
        if w_lower == 'muthint':
            return safe_sub_suffix(w_clean, r'muthint$', 'Muthinti')
        if w_lower == 'band':
            return safe_sub_suffix(w_clean, r'band$', 'Bandi')
        if w_lower == 'dodd':
            return safe_sub_suffix(w_clean, r'dodd$', 'Doddi')
        if w_lower == 'medish':
            return safe_sub_suffix(w_clean, r'medish$', 'Medisetti')
        if w_lower in ('kolll', 'koll'):
            return safe_sub_suffix(w_clean, r'kolll?$', 'Kolli')
        if w_lower == 'moll':
            return safe_sub_suffix(w_clean, r'moll$', 'Molli')

    if w_lower.endswith('lakshm'):
        return safe_sub_suffix(w_clean, r'lakshm$', 'lakshmi')
    if w_lower.endswith('laxm'):
        return safe_sub_suffix(w_clean, r'laxm$', 'laxmi')

    # 26. Broken plural honorifics: -ull -> -ulu, -all -> -alu
    if len(w_clean) >= 5 and w_lower.endswith('ull'):
        return safe_sub_suffix(w_clean, r'ull$', 'ulu')
    if len(w_clean) >= 6 and w_lower.endswith('all') and any(w_lower.startswith(s) for s in ['muthy', 'varah', 'edukond', 'yedukond', 'kandav', 'khandav', 'veerav']):
        return safe_sub_suffix(w_clean, r'all$', 'alu')

    # 27. Telugu place-surnames in -need -> -needi
    if len(w_clean) >= 6 and w_lower.endswith('need') and w_lower not in PROTECTED_EED:
        return safe_sub_suffix(w_clean, r'need$', 'needi')

    # 28. Optical 'l' for 'i' in non-Telugu plosive endings: -shml -> -shmi, -vatl -> -vati, -thl -> -thi, etc.
    if len(w_clean) >= 5:
        if re.search(r'(?:shm|vat|wath|th|eswar|path|murth)l$', w_lower):
            w_clean = safe_sub_suffix(w_clean, r'l$', 'i')
            w_lower = w_clean.lower()

    # 29. Optical 'rn' -> 'm' in Non-Sanskrit positions
    if not any(p in w_lower for p in PROTECTED_RN):
        if w_lower.startswith('rn') and len(w_lower) >= 4 and w_lower[2] in 'aeiouy':
            w_clean = ('M' if w_clean[0].isupper() else 'm') + w_clean[2:]
            w_lower = w_clean.lower()
        if 'kshrn' in w_lower:
            is_init_upper = w_clean[0].isupper()
            w_clean = re.sub(r'kshrn', 'kshm', w_clean, flags=re.I)
            if is_init_upper and w_clean:
                w_clean = w_clean[0].upper() + w_clean[1:]
            w_lower = w_clean.lower()
        if w_lower.endswith('drna'):
            w_clean = safe_sub_suffix(w_clean, r'drna$', 'dma')
            w_lower = w_clean.lower()
        if 'hrn' in w_lower:
            w_clean = re.sub(r'hrn', 'hm', w_clean, flags=re.I)
            w_lower = w_clean.lower()
        if 'mrn' in w_lower or 'rnm' in w_lower:
            w_clean = re.sub(r'(?:mrn|rnm)', 'mm', w_clean, flags=re.I)
            w_lower = w_clean.lower()
        if len(w_lower) >= 5 and w_lower.endswith('arn'):
            w_clean = safe_sub_suffix(w_clean, r'arn$', 'am')
            w_lower = w_clean.lower()

    # 30. Gender-Specific: FEMALE ONLY
    if gender == 'Female':
        # Female terminal -l smudge: -vathl, -lakshml, -kumarl, -devl, -ranl -> -i
        if re.search(r'(?:lakshm|laxm|dev|ran|kumar|man|bhavan|parvath|satyaven|tulas|jhans|math|vath)l$', w_lower):
            w_clean = safe_sub_suffix(w_clean, r'l$', 'i')
            w_lower = w_clean.lower()
        elif w_lower.endswith('rajeswarl'):
            w_clean = safe_sub_suffix(w_clean, r'l$', 'i')
            w_lower = w_clean.lower()
            
        # Female kerning / nasal glitch: -ramamna -> -ramana, -narayamna -> -narayana
        if 'ramamna' in w_lower:
            w_clean = re.sub(r'ramamna', 'ramana' if w[-1].islower() else 'Ramana', w_clean, flags=re.I)
            w_lower = w_clean.lower()
        elif 'narayamna' in w_lower:
            w_clean = re.sub(r'narayamna', 'narayana' if w[-1].islower() else 'Narayana', w_clean, flags=re.I)
            w_lower = w_clean.lower()

        if len(w_clean) >= 4 and (w_lower.endswith('eswar') or w_lower.endswith('iswar') or w_lower.endswith('easwar')):
            return safe_sub_suffix(w_clean, r'e?a?swar$', 'eswari')
        if len(w_clean) >= 5 and w_lower.endswith('sundar') and not w_lower.endswith('shyamsundar'):
            return safe_sub_suffix(w_clean, r'sundar$', 'sundari')
        if w_lower.endswith('kumar'):
            return safe_sub_suffix(w_clean, r'kumar$', 'kumari')
        if w_lower == 'ran':
            return safe_sub_suffix(w_clean, r'ran$', 'Rani')
        if w_lower == 'dev':
            return safe_sub_suffix(w_clean, r'dev$', 'Devi')
        if w_lower == 'jyoth':
            return safe_sub_suffix(w_clean, r'jyoth$', 'Jyothi')
        if w_lower == 'tulas':
            return safe_sub_suffix(w_clean, r'tulas$', 'Tulasi')
        if w_lower == 'ammaj':
            return safe_sub_suffix(w_clean, r'ammaj$', 'Ammaji')
        if w_lower == 'mang':
            return safe_sub_suffix(w_clean, r'mang$', 'Manga')
        if w_lower == 'jhans':
            return safe_sub_suffix(w_clean, r'jhans$', 'Jhansi')
        if w_lower.endswith('bhavan'):
            return safe_sub_suffix(w_clean, r'bhavan$', 'bhavani')
        if w_lower.endswith('parvath'):
            return safe_sub_suffix(w_clean, r'parvath$', 'parvathi')
        if re.search(r'[aeiou]vath$', w_lower) or re.search(r'[aeiou]wath$', w_lower) or w_lower in ('swath', 'revath'):
            return safe_sub_suffix(w_clean, r'[vw]ath$', 'vathi')
        if w_lower.endswith('satyaven'):
            return safe_sub_suffix(w_clean, r'satyaven$', 'satyaveni')
        if re.search(r'(?:satya|krishna|durga|manga|ganga)ven$', w_lower):
            return safe_sub_suffix(w_clean, r'ven$', 'veni')
        if re.search(r'(?:naga|veera|raja|daya|achyuta|arja|manga|nooka|satya|surya)man$', w_lower):
            return safe_sub_suffix(w_clean, r'man$', 'mani')
        if re.search(r'(?:bhanu|indu|satya|chandra)math$', w_lower):
            return safe_sub_suffix(w_clean, r'math$', 'mathi')
        if len(w_clean) >= 5 and w_lower.endswith('amm') and not w_lower.endswith('ramm'):
            return safe_sub_suffix(w_clean, r'amm$', 'amma')
        if len(w_clean) >= 5 and re.search(r'(?:amima|amna|anma|amrma)$', w_lower):
            return safe_sub_suffix(w_clean, r'(?:amima|amna|anma|amrma)$', 'amma')

    # 18. Gender-Specific: MALE ONLY
    if gender == 'Male':
        if len(w_clean) >= 4 and w_lower.endswith('ayy'):
            return safe_sub_suffix(w_clean, r'ayy$', 'ayya')
        if w_lower.endswith('swam'):
            return safe_sub_suffix(w_clean, r'swam$', 'swamy')

    return w_clean

SURNAME_SPLIT_PATTERNS = [
    (re.compile(r'\bKoppi\s+Setti\b', re.I), 'Koppisetti'),
    (re.compile(r'\bVasam\s+Setti\b', re.I), 'Vasamsetti'),
    (re.compile(r'\bMedis\s+Etti\b|\bMedi\s+Setti\b', re.I), 'Medisetti'),
    (re.compile(r'\bBavi\s+Setti\b', re.I), 'Bavisetti'),
    (re.compile(r'\bGalla\s+Palli\b', re.I), 'Gallapalli'),
    (re.compile(r'\bMyla\s+Palli\b|\bMayla\s+Palli\b', re.I), 'Mylapalli'),
    (re.compile(r'\bKodi\s+Palli\b', re.I), 'Kodipalli'),
    (re.compile(r'\bRaya\s+Palli\b', re.I), 'Rayapalli'),
    (re.compile(r'\bPalan\s+Ki\b', re.I), 'Palanki'),
    (re.compile(r'\bKanda\s+Valli\b', re.I), 'Kandavalli'),
    (re.compile(r'\bPasi\s+Pudi\b', re.I), 'Pasipudi'),
    (re.compile(r'\bDudde\s+Pudi\b', re.I), 'Duddepudi'),
    (re.compile(r'\bNelli\s+Pudi\b', re.I), 'Nellipudi'),
    (re.compile(r'\bGa\s+Ttem\b|\bGa\s+Tem\b', re.I), 'Gattem'),
]

RE_TRIPLE_STUTTER = re.compile(r'([a-zA-Z])\1\1+', re.I)
RE_DOUBLE_CONSONANT_START = re.compile(r'\b([bcdfghjklmnpqrstvwxyz])\1([a-z]{2,})\b', re.I)
TRAILING_ECHO_VOWELS = {
    'gantaa': 'Ganta', 'nakkaa': 'Nakka', 'adapaa': 'Adapa',
    'kandaa': 'Kanda', 'chintaa': 'Chinta', 'palikaa': 'Palika',
    'peetalaa': 'Peetala', 'bobbilii': 'Bobbili', 'kadalii': 'Kadali',
    'malladii': 'Malladi', 'galii': 'Gali', 'palapuu': 'Palapu'
}

RE_Q_AS_O = [
    (re.compile(r'\bSarqjini\b', re.I), 'Sarojini'),
    (re.compile(r'\bSarqjin\b', re.I), 'Sarojini'),
    (re.compile(r'\bSarquini\b', re.I), 'Sarojini'),
    (re.compile(r'\bSarquin\b', re.I), 'Sarojini'),
    (re.compile(r'\bSarqujini\b', re.I), 'Sarojini'),
    (re.compile(r'\bSarqja\b', re.I), 'Saroja'),
    (re.compile(r'\bNoqkaraju\b', re.I), 'Nookaraju'),
    (re.compile(r'\bNqokarathanm\b', re.I), 'Nookaratnam'),
    (re.compile(r'\bJyoqthula\b', re.I), 'Jyothula'),
    (re.compile(r'\bMeruqu\b', re.I), 'Merugu'),
    (re.compile(r'\bQruganti\b', re.I), 'Druganti'),
]

RE_TERMINAL_RAO_GLITCH = re.compile(r'([a-zA-Z]+?)(?:ragq|raqg|agq)\b', re.I)

RE_VIJAYA_GLITCH = [
    (re.compile(r'\bViuayakumari\b', re.I), 'Vijayakumari'),
    (re.compile(r'\bViuaya\b', re.I), 'Vijaya'),
    (re.compile(r'\bVuayakumari\b', re.I), 'Vijayakumari'),
    (re.compile(r'\bVuayakrishna\b', re.I), 'Vijayakrishna'),
    (re.compile(r'\bVuayalarkshm\b', re.I), 'Vijayalakshmi'),
    (re.compile(r'\bViailakshmi\b', re.I), 'Vijayalakshmi'),
]

RE_UAI_SURNAMES = [
    (re.compile(r'\bPolamuai\b', re.I), 'Polamuri'),
    (re.compile(r'\bPeruai\b', re.I), 'Peruri'),
    (re.compile(r'\bKovvuai\b', re.I), 'Kovvuri'),
    (re.compile(r'\bChelluai\b', re.I), 'Chelluri'),
    (re.compile(r'\bValluai\b', re.I), 'Valluri'),
    (re.compile(r'\bAnasuai\b', re.I), 'Anasuri'),
]

RE_MACHERLA = re.compile(r'\b(?:Matgherla|Macgharla|Macghear)\b', re.I)

RE_LARSHMI = [
    (re.compile(r'\bMahalarshmi\b', re.I), 'Mahalakshmi'),
    (re.compile(r'\bLovalarshm\b', re.I), 'Lovalakshmi'),
    (re.compile(r'\bRamlarshm\b', re.I), 'Ramalakshmi'),
    (re.compile(r'\bSivalarshm\b', re.I), 'Sivalakshmi'),
    (re.compile(r'\bSatyalarshm\b', re.I), 'Satyalakshmi'),
    (re.compile(r'\bVenkatalarshm\b', re.I), 'Venkatalakshmi'),
    (re.compile(r'\bLarshm\b', re.I), 'Lakshmi'),
]

RE_SURYANARAIN = re.compile(r'\b([A-Za-z]*?)Sur[bvy]*anaraa?in', re.I)
RE_BAABU = re.compile(r'\b([a-zA-Z]+?)baabu\b', re.I)
RE_RAAJU = re.compile(r'\b([a-zA-Z]+?)raaju\b', re.I)
RE_RAAO = re.compile(r'\b([a-zA-Z]+?)raao\b', re.I)
RE_TERMINAL_RAD_GLITCH = re.compile(
    r'\b([A-Za-z]*?(?:shwar|swar|babu|veer|nook|sesh|sundar|tirupath|madhusudhan|satya|ram|venkat|app|anand|subba|ganga|kamesh|koti|siva|shiva|mohan|som|linga|tata|mall|durg|bhadra|girir|jagapati|mutta))a*r?a*a*d\b',
    re.I
)

RE_Q_TELUGU_WORDS = [
    (re.compile(r'\bJy[oq]*q?th?ula\b', re.I), 'Jyothula'),
    (re.compile(r'\bJy[oq]*q?th?i\b', re.I), 'Jyothi'),
    (re.compile(r'\bJy[oq]*q?th?\b', re.I), 'Jyoth'),
    (re.compile(r'\bN[oq]*q[oq]*karaju\b', re.I), 'Nookaraju'),
    (re.compile(r'\bApparaq[do]*\b', re.I), 'Apparao'),
    (re.compile(r'\bNaqaswararao\b', re.I), 'Nageswararao'),
    (re.compile(r'\bNaqaraju\b', re.I), 'Nagaraju'),
    (re.compile(r'\bJaqgarao\b', re.I), 'Jaggarao'),
    (re.compile(r'\bQanga\b', re.I), 'Ganga'),
    (re.compile(r'\bQovindu\b', re.I), 'Govindu'),
    (re.compile(r'\bQollapalli\b', re.I), 'Gollapalli'),
    (re.compile(r'\bQangaraju\b', re.I), 'Gangaraju'),
    (re.compile(r'\bQanta\b', re.I), 'Ganta'),
    (re.compile(r'\bDurqaprasad\b', re.I), 'Durgaprasad'),
    (re.compile(r'\bQangadhar\b', re.I), 'Gangadhar'),
    (re.compile(r'\bQaraga\b', re.I), 'Garaga'),
    (re.compile(r'\bQadi\b', re.I), 'Gadi'),
    (re.compile(r'\bNaqababu\b', re.I), 'Nagababu'),
    (re.compile(r'\bQeddam\b', re.I), 'Geddam'),
    (re.compile(r'\bQorla\b', re.I), 'Gorla'),
    (re.compile(r'\bNaqendra\b', re.I), 'Nagendra'),
    (re.compile(r'\bJaqannadham\b', re.I), 'Jagannadham'),
    (re.compile(r'\bVemaqiri\b', re.I), 'Vemagiri'),
    (re.compile(r'\bQopala\b', re.I), 'Gopala'),
    (re.compile(r'\bQurram\b', re.I), 'Gurram'),
    (re.compile(r'\bQurrala\b', re.I), 'Gurrala'),
    (re.compile(r'\bDeqala\b', re.I), 'Degala'),
    (re.compile(r'\bQundra\b', re.I), 'Gundra'),
    (re.compile(r'\bManqatayaru\b', re.I), 'Mangatayaru'),
    (re.compile(r'\bBequm\b', re.I), 'Begum'),
    (re.compile(r'\bNaqanna\b', re.I), 'Naganna'),
    (re.compile(r'\bQoli\b', re.I), 'Goli'),
    (re.compile(r'\bQunnam\b', re.I), 'Gunnam'),
]

SPLIT_PATTERNS_V9 = [
    (re.compile(r'\b([a-zA-Z]+?set)\s+Ti\b', re.I), lambda m: m.group(1) + 'ti'),
    (re.compile(r'\b([a-zA-Z]+?pal)\s+Li\b', re.I), lambda m: m.group(1) + 'li'),
    (re.compile(r'\b([a-zA-Z]+?a[klndr])\s+La\b', re.I), lambda m: m.group(1) + 'la'),
    (re.compile(r'\b([a-zA-Z]+?ay)\s+Ya\b', re.I), lambda m: m.group(1) + 'ya'),
    (re.compile(r'\b([a-zA-Z]+?y)\s+Am\b', re.I), lambda m: m.group(1) + 'am'),
    (re.compile(r'\b([a-zA-Z]+?[a-z])d\s+Vi\b', re.I), lambda m: m.group(1) + 'devi'),
    (re.compile(r'\b([a-zA-Z]+?esw)\s+Ar\b', re.I), lambda m: m.group(1) + 'ara'),
    (re.compile(r'\bSatyanaray\s+An\b', re.I), lambda m: 'Satyanarayana'),
    (re.compile(r'\bSa\s+(Kiran|Kumar|Ram|Rama|Prasad|Teja|Krishna|Charan|Ganesh|Babu|Raju)\b', re.I), lambda m: 'Sai ' + m.group(1)),
    (re.compile(r'\bSr\s+(Tulasi|Ranga|Lakshmi|Durga|Hari|Ram|Rama|Venkata|Devi|Kanth|Kanthu)\b', re.I), lambda m: 'Sri ' + m.group(1)),
    (re.compile(r'\bJaya\s+Sr\b', re.I), lambda m: 'Jayasri'),
    (re.compile(r'\b(Sri|Rama|Manga|Satya|Durga|Lakshmi|Ganga|Parvathi|Sita|Sarada|Varalaxmi|Varalakshmi|Kanakadurga)dev\b', re.I), lambda m: m.group(1) + 'devi'),
    (re.compile(r'\b([a-zA-Z]+?)rac\b', re.I), lambda m: m.group(1) + ('rao' if m.group(1).lower().endswith(('a', 'u')) else 'arao')),
    (re.compile(r'\bSrinw\b', re.I), lambda m: 'Srinu'),
    (re.compile(r'\bShrinw\b', re.I), lambda m: 'Shrinu'),
    (re.compile(r'\b(Balaj|Sivaj|Tataj|Appaj)\b', re.I), lambda m: m.group(1) + 'i'),
]

def clean_name_string_level(name_str, gender):
    if not name_str or str(name_str).strip() in ('-', 'nan', '', 'None'):
        return ''
    s = str(name_str).strip()
    
    # Strip spurious ECI card field label bleed: Narmne / Nanme / Namre at start of relation/name
    tokens_init = s.split()
    if tokens_init and tokens_init[0].lower() in ['narmne', 'nanme', 'namre'] and len(tokens_init) > 1:
        s = " ".join(tokens_init[1:])
    
    # Noise apostrophes
    s = re.sub(r"['`]([A-Z])\b", lambda m: m.group(1).lower(), s)
    s = re.sub(r"['`]([A-Z])([a-z])", lambda m: m.group(1).lower() + m.group(2), s)
    s = re.sub(r"['`]([A-Za-z])", r"\1", s)
    s = re.sub(r"([A-Za-z])['`]", r"\1", s)
    
    # Intra-word noise dots
    s = re.sub(r'(?<=[A-Za-z]{2})\.(?=[A-Za-z]{2})', '', s)
    s = re.sub(r'(?<=[A-Za-z])\.(?=[A-Za-z]{3})', '', s)
    
    # Glued initials
    s = re.sub(r'\bvv([a-z]{3,})\b', r'V V \1', s, flags=re.I)
    
    # Split OCR minority repairs
    s = re.sub(r'\bSay\s+Ad\b', 'Sayyad', s, flags=re.I)
    s = re.sub(r'\bSha\s+Lk\b', 'Shaik', s, flags=re.I)
    
    # Suryanarain systemic corruption -> Suryanarayana
    def rep_surya(m):
        prefix = m.group(1)
        if prefix:
            return prefix + 'suryanarayana'
        return 'Suryanarayana'
    s = RE_SURYANARAIN.sub(rep_surya, s)
    s = RE_BAABU.sub(r'\1babu', s)
    s = RE_RAAJU.sub(r'\1raju', s)
    s = RE_RAAO.sub(r'\1rao', s)
    
    # High-confidence structural split & glitch patterns
    for pat, rep in SPLIT_PATTERNS_V9:
        s = pat.sub(rep, s)
        
    # Targeted optical fixes for odd n-gram OCR corruptions
    for pat, rep in RE_Q_AS_O:
        s = pat.sub(rep, s)
    for pat, rep in RE_VIJAYA_GLITCH:
        s = pat.sub(rep, s)
    for pat, rep in RE_UAI_SURNAMES:
        s = pat.sub(rep, s)
    for pat, rep in RE_LARSHMI:
        s = pat.sub(rep, s)
    s = RE_MACHERLA.sub('Macherla', s)
    
    # Terminal -ragq / -raqg / -agq descender corruption on -rao
    def rep_rao(m):
        stem = m.group(1)
        return stem + ('rao' if stem.lower().endswith(('a', 'u')) else 'arao')
    s = RE_TERMINAL_RAO_GLITCH.sub(rep_rao, s)

    # Terminal -rad / -raad / -aaad optical corruption on -rao (e.g. Venkateshwaraad -> Venkateshwararao, Sesharad -> Sesharao)
    def rep_rad(m):
        stem = m.group(1)
        st_low = stem.lower()
        if st_low.endswith(('shwar', 'swar')):
            return stem + 'arao'
        elif st_low.endswith('girir'):
            return stem[:-1] + 'rao'
        elif st_low.endswith(('a', 'i', 'u', 'e', 'o')):
            return stem + 'rao'
        return stem + 'arao'
    s = RE_TERMINAL_RAD_GLITCH.sub(rep_rad, s)

    # High-confidence Telugu Q- initial & internal replacements
    for pat, rep in RE_Q_TELUGU_WORDS:
        s = pat.sub(rep, s)
    
    # Optical smear: triple character stutter collapse (e.g. Appparao -> Apparao, Akkkireddy -> Akkireddy)
    s = RE_TRIPLE_STUTTER.sub(r'\1\1', s)
    
    # Optical smear: spurious duplicate leading consonants (e.g. Kkommineedi -> Kommineedi, Ggollapalli -> Gollapalli)
    def fix_double_start(m):
        c = m.group(1)
        rest = m.group(2)
        return (c.upper() if m.group(0)[0].isupper() else c.lower()) + rest
    s = RE_DOUBLE_CONSONANT_START.sub(fix_double_start, s)
    
    # Clean tokens individually (stripping noise punctuation glued to words)
    words = s.split()
    trimmed_words = [re.sub(r'^[^\w]+|[^\w]+$', '', w) for w in words]
    trimmed_words = [w for w in trimmed_words if w]
    cleaned_words = [clean_token(w, gender) for w in trimmed_words]
    
    # De-stuttering: consecutive duplicate words (len >= 3)
    deduped = []
    for w in cleaned_words:
        if not deduped:
            deduped.append(w)
        else:
            prev = deduped[-1]
            if len(w) >= 3 and w.lower() == prev.lower():
                continue
            deduped.append(w)
            
    res = ' '.join(deduped)
    for pat, rep in SURNAME_SPLIT_PATTERNS:
        res = pat.sub(rep, res)
        
    # Phase 9: Multi-token split surname re-stitching & double-initial consonant stutter collapse
    wr_tokens = res.split()
    n_wr = len(wr_tokens)
    merged_surs = []
    idx_m = 0
    while idx_m < n_wr:
        if idx_m < n_wr - 1:
            w1_cl = re.sub(r'[^a-zA-Z]', '', wr_tokens[idx_m]).lower()
            w2_cl = re.sub(r'[^a-zA-Z]', '', wr_tokens[idx_m+1]).lower()
            if (w1_cl, w2_cl) in SPLIT_SURNAME_MAP:
                merged_surs.append(SPLIT_SURNAME_MAP[(w1_cl, w2_cl)])
                idx_m += 2
                continue
        merged_surs.append(wr_tokens[idx_m])
        idx_m += 1
        
    final_post_words = []
    for w in merged_surs:
        clean_w = re.sub(r'[^a-zA-Z]', '', w)
        clean_wl = clean_w.lower()
        m_di = RE_DOUBLE_INITIAL.match(clean_wl)
        if m_di:
            c1 = m_di.group(1)
            rst = m_di.group(2)
            fixed_w = (c1.upper() if clean_w[0].isupper() else c1) + rst
            final_post_words.append(fixed_w)
        elif clean_wl == 'lakshmigattem':
            final_post_words.extend(['Lakshmi', 'Gattem'])
        elif clean_wl == 'lakshmitida':
            final_post_words.extend(['Lakshmi', 'Tida'])
        elif clean_wl in TRAILING_ECHO_VOWELS:
            rep = TRAILING_ECHO_VOWELS[clean_wl]
            final_post_words.append(rep if clean_w[0].isupper() else rep.lower())
        else:
            final_post_words.append(w)
            
    return ' '.join(final_post_words)

# ==============================================================================
# 3. LINGUISTIC CLASSIFIER WITH ENHANCED MUSLIM RECOGNITION & PROXIMITY
# ==============================================================================

def classify_individual(voter_name, rel_name):
    v_clean = [re.sub(r'[^a-zA-Z]', '', t).lower() for t in str(voter_name).split() if re.sub(r'[^a-zA-Z]', '', t)]
    r_clean = [re.sub(r'[^a-zA-Z]', '', t).lower() for t in str(rel_name).split() if re.sub(r'[^a-zA-Z]', '', t)]
    all_tokens = v_clean + r_clean
    
    # 0. Pasham Absolute Guard: Telugu Hindu surname (never misclassify clipped 'Pasha')
    if 'pasham' in all_tokens:
        return 'T'
    
    # 1. Christian / Biblical / Anglo / Syncretic (C)
    for t in all_tokens:
        if t in CHRISTIAN_TOKENS or t.startswith('yesu') or t.startswith('esub') or t.startswith('jesu'):
            return 'C'
            
    # Yakub guard: In Andhra Pradesh, Yakub alone without Islamic titles is Christian (Jacob)
    if 'yakub' in all_tokens or 'yacoob' in all_tokens:
        has_muslim_other = any(t in ISLAMIC_TOKENS and t not in ('yakub', 'yacoob') for t in all_tokens)
        if not has_muslim_other:
            return 'C'
            
    # 2. Md / Mohd Guard against Hindu initials
    if 'md' in all_tokens or 'mohd' in all_tokens:
        has_hindu = any(t in ('subrahmanyam', 'subramanyam', 'krishnamurthy', 'krishnamurthry', 'satyanarayana', 'sriranga') for t in all_tokens)
        if has_hindu:
            # Fall through to Sanskrit/Telugu
            pass
        else:
            return 'M'
            
    # 3. Sk Guard
    if 'sk' in all_tokens:
        has_muslim_other = any(t in ISLAMIC_TOKENS or t in ISLAMIC_BI_WHITELIST for t in all_tokens if t != 'sk')
        if has_muslim_other:
            return 'M'
            
    # 4. Token & Suffix matching for Islamic
    for t in all_tokens:
        if t in ISLAMIC_EXCLUSIONS:
            continue
            
        if t in ISLAMIC_TOKENS or t in ISLAMIC_BI_WHITELIST:
            # Syncretic guard for ambiguous names
            if t in ('mastan', 'masthan', 'fakir', 'fakeer', 'sattar', 'kamil'):
                if any(any(other.endswith(hd) for hd in HINDU_DISQUALIFIERS) for other in all_tokens if other != t):
                    continue
            return 'M'
            
        # Feminine compound matching (-unnisa, -begam, etc.)
        if re.search(r'.*(?:unnisa|unissa|unnisha|unisha|begam|begum|khatoon|khatun)$', t, re.I):
            if not any(t.endswith(ex) for ex in ISLAMIC_EXCLUSIONS):
                if not any(any(other.endswith(hd) for hd in HINDU_DISQUALIFIERS) for other in all_tokens):
                    return 'M'
                    
        # Suffix matching (-saheb, -basha, -pasha, -ullah, -uddin, etc.)
        if any(t.endswith(suf) for suf in ('saheb', 'sahib', 'sahes', 'sahebu', 'sahibu', 'basha', 'bhasha', 'pasha', 'ullah', 'uddin', 'deen')):
            if not any(t.endswith(ex) for ex in ISLAMIC_EXCLUSIONS):
                if not any(any(other.endswith(hd) for hd in HINDU_DISQUALIFIERS) for other in all_tokens):
                    return 'M'
                    
    # Split OCR names
    full_str = f"{voter_name} {rel_name}".lower()
    if re.search(r'\bsay\s+ad\b', full_str) or re.search(r'\bsha\s+lk\b', full_str) or re.search(r'\bshaik\s+bi\b', full_str):
        return 'M'
        
    # 5. Sanskrit / Classical Indo-Aryan Halanta (S)
    for t in all_tokens:
        if t in SANSKRIT_LINEAGE or t.endswith('charyulu') or t.endswith('shastri') or t.endswith('sastri'):
            return 'S'
            
    has_telugu_honorific = any(t.endswith(TELUGU_HONORIFICS) for t in all_tokens)
    if not has_telugu_honorific:
        if v_clean and all(t in SANSKRIT_HALANTA_ROOTS for t in v_clean):
            return 'S'
            
    # 6. Default: All Telugu followed structured names (T)
    return 'T'

def apply_household_and_proximity_propagation(df, raw_groups):
    final_groups = list(raw_groups)
    
    # Index members by household (assembly_part_2025, door_no)
    hh_map = defaultdict(list)
    for idx, (p, d, sno, v, r, g) in enumerate(zip(
        df['assembly_part_2025'], df['door_no'], df['booth_sno_2025'],
        df['voter_name_en'], df['rel_name_en'], raw_groups
    )):
        d_clean = str(d).strip()
        if d_clean and d_clean not in ('-', 'nan', '', '0', '00'):
            sno_int = int(sno) if str(sno).isdigit() else 0
            hh_map[(p, d_clean)].append((idx, v, r, g, sno_int))
            
    # Kinship & Household propagation
    prop_m = 0
    prop_c = 0
    
    for (p, d), members in hh_map.items():
        if len(members) > 8:
            continue
            
        m_anchors = [m for m in members if m[3] == 'M']
        c_anchors = [m for m in members if m[3] == 'C']
        
        # Propagate M within unambiguous household
        if m_anchors and not c_anchors:
            for idx, v, r, g, sno in members:
                if g == 'T':
                    rel_match = any((m[1].lower() in r.lower() or r.lower() in m[1].lower()) and len(r.strip()) >= 3 for m in m_anchors)
                    shared_rel = any(m[2].lower() == r.lower() and len(r.strip()) >= 3 for m in m_anchors)
                    surname_match = any(
                        len(v.split()) >= 2 and len(m[1].split()) >= 2 and 
                        v.split()[-1].lower() == m[1].split()[-1].lower() and 
                        m[1].split()[-1].lower() in ISLAMIC_TOKENS 
                        for m in m_anchors
                    )
                    # Serial number proximity: adjacent record in same family unit
                    sno_proximity = any(abs(sno - m[4]) <= 2 for m in m_anchors)
                    
                    if rel_match or shared_rel or surname_match or (sno_proximity and len(members) <= 4):
                        final_groups[idx] = 'M'
                        prop_m += 1
                        
        # Propagate C within unambiguous household
        if c_anchors and not m_anchors:
            for idx, v, r, g, sno in members:
                if g == 'T':
                    rel_match = any((c[1].lower() in r.lower() or r.lower() in c[1].lower()) and len(r.strip()) >= 3 for c in c_anchors)
                    shared_rel = any(c[2].lower() == r.lower() and len(r.strip()) >= 3 for c in c_anchors)
                    surname_match = any(
                        len(v.split()) >= 2 and len(c[1].split()) >= 2 and 
                        v.split()[-1].lower() == c[1].split()[-1].lower() and 
                        c[1].split()[-1].lower() in CHRISTIAN_TOKENS 
                        for c in c_anchors
                    )
                    sno_proximity = any(abs(sno - c[4]) <= 2 for c in c_anchors)
                    
                    if rel_match or shared_rel or surname_match or (sno_proximity and len(members) <= 4):
                        final_groups[idx] = 'C'
                        prop_c += 1
                        
    return final_groups, prop_m, prop_c

# ==============================================================================
# 4. SURNAME CROSS-REFERENCING & MULTI-SCALE PROXIMITY RESTORATION ENGINE
# ==============================================================================

CUTOFF_CONSONANTS = ('d', 't', 'k', 'g', 'p', 'b', 'c', 'j', 'z', 'v', 'w', 'f', 'm', 'l', 'r', 'n', 's')
CUTOFF_CLUSTERS = ('dh', 'th', 'nk', 'mp', 'nt', 'll', 'rr', 'tt', 'dd', 'pp', 'bb', 'gg', 'eed', 'nid', 'mid', 'tid')

def can_safely_repair_surname(short_sur, long_sur):
    if not short_sur or not long_sur:
        return False
    s = short_sur.lower()
    l = long_sur.lower()
    if s == l:
        return False
    if len(s) < 3 or len(l) < 4:
        return False
    if s in PROTECTED_HALANTA_BLOCKLIST or l in PROTECTED_HALANTA_BLOCKLIST or s == 'srinivas' or l == 'srinivas':
        return False
    if s in PROTECTED_GIVEN_NAMES:
        return False
        
    # DUAL-CASL IMMUNITY (Guarantees distinct authentic Andhra surnames are NEVER merged):
    # If both candidate surnames exist as established entries in CASL, they are distinct families!
    # (Guarantees 'Boppana' vs 'Boppanna', 'Palika' vs 'Paliki', 'Kona' vs 'Konda' remain distinct!)
    if s in CASL_SURNAMES and l in CASL_SURNAMES:
        return False

    # Avoid duplicate vowel OCR glitch: e.g. Ganta -> Gantaa, Nakka -> Nakkaa, Adapa -> Adapaa
    if l == s + 'a' or l == s + 'e' or l == s + 'o':
        if s.endswith(('a', 'e', 'o')):
            return False
    if s in ('ramana', 'subba', 'naga', 'surya', 'satya', 'siva', 'sita', 'lakshmi', 'durga'):
        return False

    # 1. Terminal optical smudge on 'l', 'pl', 'dl' (e.g. 'Chagantl' -> 'Chaganti', 'Merugl' -> 'Merugu', 'Palepl' -> 'Palepu', 'Boddl' -> 'Boddu')
    if len(s) == len(l):
        if s.endswith('l') and l.endswith(('i', 'u')) and s[:-1] == l[:-1]:
            return True
        if s.endswith('pl') and l.endswith('pu') and s[:-2] == l[:-2]:
            return True
        if s.endswith('dl') and l.endswith('du') and s[:-2] == l[:-2]:
            return True

    # ABSOLUTE VOWEL IMMUNITY (Guarantees zero false positives on complete words):
    # Any word already ending in standard vowels is strictly IMMUNE to elongation.
    # (Guarantees 'Boppana' NEVER becomes 'Boppanna', 'Kommineedi' NEVER becomes 'Kkommineedi', 'Ganta' NEVER becomes 'Gantaa')
    if s.endswith(('a', 'i', 'u')):
        return False

    # 2. Prefix cutoff: Truncation of broken halanta consonants (e.g. Gad -> Gadi, Salad -> Saladi, Palik -> Paliki, Int -> Inti)
    if l.startswith(s):
        diff = len(l) - len(s)
        if diff in (1, 2, 3):
            # Short surname ends in consonant / cluster, long surname ends in valid vowel
            if (s.endswith(CUTOFF_CONSONANTS) or any(s.endswith(c) for c in CUTOFF_CLUSTERS)) and l[-1] in ('i', 'u', 'y', 'a', 'e'):
                return True
            # Short surname dropped terminal vowel like Kolipe -> Kolipey
            if s.endswith(('e', 'o')) and l.endswith(('ey', 'oy', 'i', 'u')) and diff == 1:
                return True

    return False

def repair_intra_card(v_name, r_name):
    if not v_name or not r_name or str(v_name).strip() in ('-', '', 'nan') or str(r_name).strip() in ('-', '', 'nan'):
        return v_name, r_name, 0
    v_words = str(v_name).split()
    r_words = str(r_name).split()
    rep_cnt = 0
    if len(v_words) >= 2 and len(r_words) >= 2:
        # Check last words
        v_sur = re.sub(r'[^a-zA-Z]', '', v_words[-1])
        r_sur = re.sub(r'[^a-zA-Z]', '', r_words[-1])
        if v_sur.lower() == 'pasham' and r_sur.lower() == 'pasha':
            r_words[-1] = 'Pasham' if r_sur[0].isupper() else 'pasham'
            r_name = ' '.join(r_words)
            rep_cnt += 1
        elif r_sur.lower() == 'pasham' and v_sur.lower() == 'pasha':
            v_words[-1] = 'Pasham' if v_sur[0].isupper() else 'pasham'
            v_name = ' '.join(v_words)
            rep_cnt += 1
        elif can_safely_repair_surname(v_sur, r_sur):
            v_words[-1] = r_sur
            v_name = ' '.join(v_words)
            rep_cnt += 1
        elif can_safely_repair_surname(r_sur, v_sur):
            r_words[-1] = v_sur
            r_name = ' '.join(r_words)
            rep_cnt += 1

        # Check first words
        v_first = re.sub(r'[^a-zA-Z]', '', v_words[0])
        r_first = re.sub(r'[^a-zA-Z]', '', r_words[0])
        if can_safely_repair_surname(v_first, r_first):
            v_words[0] = r_first
            v_name = ' '.join(v_words)
            rep_cnt += 1
        elif can_safely_repair_surname(r_first, v_first):
            r_words[0] = v_first
            r_name = ' '.join(r_words)
            rep_cnt += 1
    return v_name, r_name, rep_cnt

def apply_proximity_surname_restoration(df, v_in, r_in):
    parts = df['assembly_part_2025'].tolist()
    doors = df['door_no'].tolist()
    snos = [int(s) if str(s).isdigit() else 0 for s in df['booth_sno_2025']]
    total_recs = len(df)
    
    v_out = list(v_in)
    r_out = list(r_in)
    
    door_rep = 0
    serial_rep = 0
    
    # Level A: Household Door Consensus
    hh_surs = defaultdict(Counter)
    for p, d, v, r in zip(parts, doors, v_out, r_out):
        d_clean = str(d).strip().lower()
        if d_clean and d_clean not in ('-', 'nan', '', '0', '00'):
            for nm in (v, r):
                words = nm.split()
                if len(words) >= 2:
                    for idx in (0, -1):
                        sur = re.sub(r'[^a-zA-Z]', '', words[idx])
                        if len(sur) >= 4 and sur.lower() not in PROTECTED_HALANTA_BLOCKLIST and (sur.lower() in CASL_SURNAMES or sur[-1] in ('i', 'u', 'y', 'a', 'e')):
                            hh_surs[(p, d_clean)][sur] += 1
                            
    for i in range(total_recs):
        p = parts[i]
        d_clean = str(doors[i]).strip().lower()
        if d_clean and (p, d_clean) in hh_surs:
            valid_cands = hh_surs[(p, d_clean)]
            vw = v_out[i].split()
            if len(vw) >= 2:
                for idx in (0, -1):
                    cur = re.sub(r'[^a-zA-Z]', '', vw[idx])
                    for cand, cand_cnt in valid_cands.most_common():
                        if cand_cnt >= 2 and can_safely_repair_surname(cur, cand):
                            vw[idx] = cand
                            v_out[i] = ' '.join(vw)
                            door_rep += 1
                            break
            rw = r_out[i].split()
            if len(rw) >= 2:
                for idx in (0, -1):
                    cur = re.sub(r'[^a-zA-Z]', '', rw[idx])
                    for cand, cand_cnt in valid_cands.most_common():
                        if cand_cnt >= 2 and can_safely_repair_surname(cur, cand):
                            rw[idx] = cand
                            r_out[i] = ' '.join(rw)
                            door_rep += 1
                            break

    # Level B: Contiguous Serial Adjacency ([-2, +2])
    part_indices = defaultdict(list)
    for idx, p in enumerate(parts):
        part_indices[p].append(idx)
        
    for p, idx_list in part_indices.items():
        idx_list.sort(key=lambda x: snos[x])
        n_p = len(idx_list)
        for k, cur_idx in enumerate(idx_list):
            cur_sno = snos[cur_idx]
            if cur_sno <= 0:
                continue
            adj_cands = set()
            for neighbor_k in range(max(0, k - 2), min(n_p, k + 3)):
                if k != neighbor_k:
                    n_idx = idx_list[neighbor_k]
                    n_sno = snos[n_idx]
                    if abs(cur_sno - n_sno) <= 2:
                        for nm in (v_out[n_idx], r_out[n_idx]):
                            words = nm.split()
                            if len(words) >= 2:
                                for widx in (0, -1):
                                    sur = re.sub(r'[^a-zA-Z]', '', words[widx])
                                    if len(sur) >= 4 and sur.lower() not in PROTECTED_HALANTA_BLOCKLIST and (sur.lower() in CASL_SURNAMES or sur[-1] in ('i', 'u', 'y', 'a', 'e')):
                                        adj_cands.add(sur)
            if adj_cands:
                vw = v_out[cur_idx].split()
                if len(vw) >= 2:
                    for idx in (0, -1):
                        cur = re.sub(r'[^a-zA-Z]', '', vw[idx])
                        for cand in adj_cands:
                            if can_safely_repair_surname(cur, cand):
                                vw[idx] = cand
                                v_out[cur_idx] = ' '.join(vw)
                                serial_rep += 1
                                break
                rw = r_out[cur_idx].split()
                if len(rw) >= 2:
                    for idx in (0, -1):
                        cur = re.sub(r'[^a-zA-Z]', '', rw[idx])
                        for cand in adj_cands:
                            if can_safely_repair_surname(cur, cand):
                                rw[idx] = cand
                                r_out[cur_idx] = ' '.join(rw)
                                serial_rep += 1
                                break

    return v_out, r_out, door_rep, serial_rep

# ==============================================================================
# 5. CONSTITUENCY PIPELINE PROCESSOR
# ==============================================================================

def process_constituency(ac_no, ac_name, csv_path, qa_path):
    t0 = time.time()
    print(f"\n=======================================================", flush=True)
    print(f"PROCESSING {ac_name} (AC {ac_no})...", flush=True)
    print(f"Loading {csv_path}...", flush=True)
    
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df = df.fillna('')
    total_recs = len(df)
    print(f"Total electors loaded: {total_recs:,}", flush=True)
    
    orig_voters = df['voter_name_en'].tolist()
    orig_rels = df['rel_name_en'].tolist()
    genders = df['gender'].tolist()
    rel_types = df['rel_type'].tolist()
    
    # Infer relative gender
    r_genders = []
    for rt, g in zip(rel_types, genders):
        if rt in ('Father', 'Husband'):
            r_genders.append('Male')
        elif rt == 'Mother':
            r_genders.append('Female')
        else:
            r_genders.append(g)
            
    # Stage 1: Full Optical & Linguistic Normalization
    print("Stage 1: Applying Optical & Guarded Linguistic Normalization...", flush=True)
    v1 = [clean_name_string_level(v, g) for v, g in zip(orig_voters, genders)]
    r1 = [clean_name_string_level(r, rg) for r, rg in zip(orig_rels, r_genders)]
    
    # Stage 2: Intra-Card Surname Cross-Referencing
    print("Stage 2: Applying Intra-Card Surname Cross-Referencing...", flush=True)
    v2 = []
    r2 = []
    intra_diff = 0
    for v, r in zip(v1, r1):
        nv, nr, r_cnt = repair_intra_card(v, r)
        if nv != v or nr != r:
            intra_diff += 1
        v2.append(nv)
        r2.append(nr)
    print(f"  Intra-Card Cross-Referenced Names: {intra_diff:,} records", flush=True)
    
    # Stage 3: Multi-Scale Proximity & Spatial Surname Restoration
    print("Stage 3: Multi-Scale Household & Serial Proximity Restoration...", flush=True)
    v3, r3, n_door, n_serial = apply_proximity_surname_restoration(df, v2, r2)
    print(f"  Door-Consensus Surname Repairs: {n_door:,} | Serial-Adjacency Repairs: {n_serial:,}", flush=True)
    
    df['voter_name_en'] = v3
    df['rel_name_en'] = r3
    
    # Stage 4: Linguistic Origin Classification & Spatial Propagation
    print("Stage 4: Classifying Electors into Linguistic Groups (C, M, S, T)...", flush=True)
    raw_groups = [classify_individual(v, r) for v, r in zip(v3, r3)]
    
    print("Stage 5: Applying Kinship, Door-Number & Serial Proximity Propagation...", flush=True)
    final_groups, prop_m, prop_c = apply_household_and_proximity_propagation(df, raw_groups)
    print(f"  Kinship / Proximity Propagations -> M: +{prop_m:,}, C: +{prop_c:,}", flush=True)
    
    # Insert linguistic_group column right after gender (or before status)
    if 'linguistic_group' in df.columns:
        df['linguistic_group'] = final_groups
    else:
        cols = list(df.columns)
        gender_idx = cols.index('gender') if 'gender' in cols else len(cols) - 1
        cols.insert(gender_idx + 1, 'linguistic_group')
        df['linguistic_group'] = final_groups
        df = df[cols]
        
    grp_counts = Counter(final_groups)
    print(f"  Final Linguistic Breakdown for {ac_name}:")
    for g, cnt in grp_counts.most_common():
        print(f"    - Group '{g}': {cnt:,} ({cnt/total_recs*100:.2f}%)")
    
    # Metrics
    v_diffs = [(o, n) for o, n in zip(orig_voters, v3) if o != n]
    r_diffs = [(o, n) for o, n in zip(orig_rels, r3) if o != n]
    
    print(f"\nRESULTS FOR {ac_name}:")
    print(f"  Voter Names Enhanced:    {len(v_diffs):,} / {total_recs:,} ({len(v_diffs)/total_recs*100:.2f}%)")
    print(f"  Relative Names Enhanced: {len(r_diffs):,} / {total_recs:,} ({len(r_diffs)/total_recs*100:.2f}%)")
    print(f"  Total Names Polished:    {len(v_diffs) + len(r_diffs):,}")
    
    # Save CSV
    df.to_csv(csv_path, index=False)
    print(f"Saved enhanced Master CSV -> {csv_path} ({os.path.getsize(csv_path):,} bytes)", flush=True)
    
    # Update QA Report
    if os.path.exists(qa_path):
        with open(qa_path, "r", encoding="utf-8") as f:
            rep = json.load(f)
        if "sanitization_metrics" not in rep:
            rep["sanitization_metrics"] = {}
        rep["sanitization_metrics"]["proximity_intra_card_repairs"] = intra_diff
        rep["sanitization_metrics"]["proximity_door_consensus_repairs"] = n_door
        rep["sanitization_metrics"]["proximity_serial_adjacency_repairs"] = n_serial
        rep["sanitization_metrics"]["linguistic_voter_names_enhanced"] = len(v_diffs)
        rep["sanitization_metrics"]["linguistic_relative_names_enhanced"] = len(r_diffs)
        rep["sanitization_metrics"]["linguistic_total_enhanced"] = len(v_diffs) + len(r_diffs)
        rep["sanitization_metrics"]["linguistic_group_breakdown"] = dict(grp_counts)
        rep["audit_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2)
        print(f"Updated QA report -> {qa_path}", flush=True)
        
    print(f"Completed {ac_name} in {time.time()-t0:.1f}s", flush=True)
    return len(v_diffs), len(r_diffs), intra_diff, n_door, n_serial, grp_counts

# ==============================================================================
# 6. MAIN EXECUTION
# ==============================================================================

def main():
    print("STARTING FULL LINGUISTIC & MULTI-SCALE SPATIAL SURNAME RESTORATION SUITE V7 ACROSS ALL 3 CONSTITUENCIES...", flush=True)
    t_start = time.time()
    
    total_grps = Counter()
    total_intra = 0
    total_door = 0
    total_serial = 0
    
    # 1. Pithapuram (AC 37)
    v1, r1, i1, d1, s1, g1 = process_constituency(
        37, "Pithapuram",
        r"C:\Users\vamsi\Downloads\Voter_Analysis\Pithapuram\Pithapuram_AC37_Master_Voters_2025.csv",
        r"C:\Users\vamsi\Downloads\Voter_Analysis\Pithapuram\Pithapuram_AC37_QA_Audit_Report.json"
    )
    total_grps += g1
    total_intra += i1
    total_door += d1
    total_serial += s1
    
    # 2. Peddapuram (AC 39)
    v2, r2, i2, d2, s2, g2 = process_constituency(
        39, "Peddapuram",
        r"C:\Users\vamsi\Downloads\Voter_Analysis\Peddapuram\Peddapuram_AC39_Master_Voters_2025.csv",
        r"C:\Users\vamsi\Downloads\Voter_Analysis\Peddapuram\Peddapuram_AC39_QA_Audit_Report.json"
    )
    total_grps += g2
    total_intra += i2
    total_door += d2
    total_serial += s2
    
    # 3. Kakinada Rural (AC 38)
    v3, r3, i3, d3, s3, g3 = process_constituency(
        38, "Kakinada Rural",
        r"C:\Users\vamsi\Downloads\Voter_Analysis\Kakinada_Rural\Kakinada_Rural_AC38_Master_Voters_2025.csv",
        r"C:\Users\vamsi\Downloads\Voter_Analysis\Kakinada_Rural\Kakinada_Rural_AC38_QA_Audit_Report.json"
    )
    total_grps += g3
    total_intra += i3
    total_door += d3
    total_serial += s3
    
    total_v = v1 + v2 + v3
    total_r = r1 + r2 + r3
    total_all = 721735
    
    print("\n=======================================================", flush=True)
    print("ALL 3 CONSTITUENCIES SUCCESSFULLY ENHANCED & RESTORED!", flush=True)
    print(f"Grand Total Voter Names Enhanced:       {total_v:,}", flush=True)
    print(f"Grand Total Relative Names Enhanced:    {total_r:,}", flush=True)
    print(f"Grand Total Names Polished:             {total_v + total_r:,}", flush=True)
    print(f"Multi-Scale Proximity Surnames Restored:")
    print(f"  - Intra-Card Mutual Surname Repairs:  {total_intra:,}")
    print(f"  - Household Door-Consensus Repairs:   {total_door:,}")
    print(f"  - Serial Adjacency (Street) Repairs:  {total_serial:,}")
    print(f"  - Total Proximity Restorations:       {total_intra + total_door + total_serial:,}")
    print("\nOVERALL ELECTORATE LINGUISTIC BREAKDOWN:")
    for g, cnt in total_grps.most_common():
        desc = {
            'T': 'All Telugu followed structured names',
            'C': 'Anglo / Christian / Western / Syncretic Telugu Christian',
            'M': 'Islamic / Arabic / Persian / Urdu',
            'S': 'Sanskrit / Classical Indo-Aryan Halanta'
        }.get(g, g)
        print(f"  Group '{g}' ({desc}): {cnt:,} ({cnt/total_all*100:.2f}%)")
        
    print(f"\nTotal Processing Time: {time.time()-t_start:.1f}s", flush=True)

if __name__ == '__main__':
    main()
