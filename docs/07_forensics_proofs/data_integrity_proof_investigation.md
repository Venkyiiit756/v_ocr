# Independent Forensic Audit of the Previous "Proof Investigation" Report

To perform a strictly unbiased audit of the previous report, we visually inspected the actual cropped card PNGs (`read_file` on the images rather than relying only on raw Tesseract text dumps) and traced the exact execution of [`engine.py`](file:///C:/Users/vamsi/.gemini/antigravity/scratch/peddapuram_electoral_mapping/electoral_engine/engine.py) and [`parser.py`](file:///C:/Users/vamsi/.gemini/antigravity/scratch/peddapuram_electoral_mapping/electoral_engine/parser.py).

> [!CAUTION]
> **Audit Verdict on the Previous Report:** **Partially Invalid / Confirmatory Bias Detected.**
> Several key claims in the previous report were **factually incorrect** because the quick proof script relied on raw full-card OCR dumps without looking at the actual card images, had a page-index drift bug (`2 + (sno - 1) // 30`), and missed a genuine regex bug in `parser.py`.

---

## Finding 1: The Claim That "EPICs Literally Do Not Exist in the Source PDFs" is **FALSE**

### What the Previous Report Claimed
The previous report claimed that on Part 1 Serial 20, 723, and 872, the Election Commission omitted the EPIC line entirely and the card started with `Name : ...`.

### What Visual Inspection of the Actual Card Images Proves
When we open the actual PNG images of the true cards for Serial 20, 339, 415, 723, 872, and 1063 in Part 1, **100% of them have a clearly printed EPIC number in the top-right corner**:

````carousel
![True Part 1 Sno 20](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/full_card_20.png)
<!-- slide -->
![True Part 1 Sno 339](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/TRUE_EPIC_Part1_Sno339.png)
<!-- slide -->
![True Part 1 Sno 415](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/TRUE_EPIC_Part1_Sno415.png)
<!-- slide -->
![True Part 1 Sno 723](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/TRUE_EPIC_Part1_Sno723.png)
<!-- slide -->
![True Part 1 Sno 872](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/TRUE_EPIC_Part1_Sno872.png)
<!-- slide -->
![True Part 1 Sno 1063](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/TRUE_EPIC_Part1_Sno1063.png)
````

### Why the Previous Report Got Fooled (Two Mistakes)
1. **Full-Card `--psm 6` Layout Blindness:** The previous proof script ran `tesseract full_card_20.png stdout --psm 6` on the whole uncropped card. Because there is a black rectangular box around `[ 20 ]` on the top-left and white space in the middle, Tesseract's `--psm 6` layout analyzer treated the entire top row as a table border and skipped `YOU1474972` completely. The author read the Tesseract text output without looking at the PNG image and wrongly concluded the EPIC wasn't printed on the PDF.
2. **Page-Offset Drift:** The previous script used `pno = 2 + (sno - 1) // 30` assuming every page had 30 cards. Because earlier pages had <30 cards, its crops for `723`, `872`, and `415` were actually cards `702`, `851`, and `401`.

### Why the Real Pipeline (`engine.py`) Actually Missed Those 6 EPICs
Tracing `ElectoralPipelineEngine` on those 6 true cards reveals the **actual** technical cause:
| Serial | True Printed EPIC | What `engine.py` Read at 200 DPI | True Technical Cause of Rejection |
| :--- | :--- | :--- | :--- |
| **Sno 20** | `YOU1474972` | `YOUM/4972` / `YOUN 74972` | **Kerning fusion:** Tight `14` fused into a single letter `M` or `N`, shortening the string from 10 chars to 9 chars (`YOU` + 6 digits). |
| **Sno 339** | `YOU1480433` | `YOUMs0433` / `YOUMEe0 433` | **Kerning fusion:** Tight `14` fused into `M`, shortening the suffix to 6 digits. |
| **Sno 415** | `YOU1568963` | `YOUS68963` / `YOUTSSS963` | `1` dropped in pass 1 (9 chars); in pass 2 (`YOUTSSS963`), `YOU` + 8 chars didn't match the `YOUN/YOUI` prefix strip rule for `YOUT`. |
| **Sno 723** | `YOU1570886` | `YOUTH 7/0886` / `YOUNS70886` | **Kerning fusion:** `1` merged with `YOU` (`YOUN`), leaving 6 suffix digits (`S70886`). |
| **Sno 872** | `YOU0995433` | `YOU09C5433` / `YOU09P5433` | Second `9` has a slight gap and was read as `C` or `P`, neither of which is in `epic_char_subs`. |
| **Sno 1063** | `YOU0855561` | `YOUO0BR55541` / `YOQUOESS561` | `8` was split into `BR` (11 chars) or read as `E` with prefix `YOQUO` (not matched by `YOQU` rule). |

---

## Finding 2: ~85% of "Missing Ages" Are Caused by a Greedy Regex Bug in `parser.py` That Swallows Ages 18 and 19!

### What the Previous Report Claimed
The previous report claimed missing ages were mostly optical punctuation typos (`Age ? 27`, `Age :. 56`).

### What the Independent Audit Found
When we inspected the **true** missing-age cards in Part 1 (`Sno 64, 480, 670, 804, 826, 1073`), **every single one of them was a 19-year-old voter (`Age : 19`)**!

![True Part 1 Sno 64](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/TRUE_AGE_Part1_Sno64.png)

Why did [`parser.py` (line 289)](file:///C:/Users/vamsi/.gemini/antigravity/scratch/peddapuram_electoral_mapping/electoral_engine/parser.py#L289) return `None` for clean text reading `Age : 19 Gender : Male`?
Look at the regex in [`parser.py` line 289](file:///C:/Users/vamsi/.gemini/antigravity/scratch/peddapuram_electoral_mapping/electoral_engine/parser.py#L289):
```python
r'(?:^|(?<=[\s\n\r0-9]))(?:[0-9]?Ag[e\?@aoc]|Age|Vayassu)\b\s*[:*+=;>?\-\.\'\"it1l|/\\!\}\]\s]{0,6}([0-9OQoDBSlI|Z/\?d#A]{1,4})'
```
* Notice that **`1`, `l`, `|` are inside the greedy separator character class** `[:*+=;>?\-\.\'\"it1l|/\\!\}\]\s]{0,6}` right before the age capture group!
* Whenever a voter is **18 or 19 years old** (`Age : 18` or `Age : 19`), the greedy separator class `[:...1...]{0,6}` **swallows `: 1`**, leaving only `8` or `9` for the capture group!
* Then `if 18 <= val <= 110:` rejects `8` and `9` as `< 18`, wiping out the age!

**Proof Across the 3 Master CSVs:**
* **Peddapuram (AC 39)** *(run before `1` was added to the separator regex)*: **1,846** voters aged 18–19; only **385** missing ages (**99.82% complete**).
* **Pithapuram (AC 37)** *(run after `1` was added to the separator regex)*: **0** voters aged 18, **94** aged 19; **2,322** missing ages (~1,900 of which are 18–19 year olds swallowed by this regex!).
* **Kakinada Rural (AC 38)**: **0** voters aged 18, **79** aged 19; **2,917** missing ages (~2,400 of which are 18–19 year olds swallowed by this regex!).

---

## Finding 3: What Happens with Missing Door Numbers (`DELETED` Stamps vs. True Blanks)

Visually inspecting the three Door Number proof images (`door_proof_397.png`, `door_proof_127.png`, `door_proof_75.png`) shows two distinct realities:

````carousel
![Part 2 Sno 397](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/door_proof_397.png)
<!-- slide -->
![Part 4 Sno 127](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/door_proof_127.png)
<!-- slide -->
![Part 4 Sno 75](/C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/door_proof_75.png)
````

1. **True Source Anomaly (`door_proof_397.png` — Valid Claim):** Part 2, Serial 397 genuinely prints `House Number : house` in the official ECI PDF. Since `clean_door` requires at least one digit, it rightly outputs `-`.
2. **Diagonal `DELETED` Stamp Occlusion (`door_proof_127.png` & `door_proof_75.png` — Misdiagnosed in Previous Report):**
   * The previous report claimed Part 4, Serial 127 was printed as `"House Number : NO /"` (No House Number).
   * **Visual truth:** The card actually prints `House Number : 1-21/J`, and a large diagonal **`DELETED`** stamp crosses directly over `1-21/`, causing OCR to read `NO J`!
   * Similarly, on Part 4, Serial 75, the card prints `House Number : 1-19`, and the diagonal **`DELETED`** stamp crosses right over `19`, leaving `1-`.
   * Furthermore, because the `DELETED` stamp is diagonal and broken across text lines, those rows were still marked `status = Active` in the CSV!
