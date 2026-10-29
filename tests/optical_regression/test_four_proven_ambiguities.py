import pandas as pd

pitha = pd.read_csv(r'C:\Users\vamsi\Downloads\Voter_Analysis\Pithapuram\Pithapuram_AC37_Master_Voters_2025.csv', low_memory=False)

cases = [
    (6, 595, 'Case 1: Apparao Nakka'),
    (241, 265, 'Case 2: Chellarao Pediredla'),
    (109, 603, 'Case 3: Chellarao Medisetti'),
    (96, 356, 'Case 4: Chellarao Ketinidi')
]

for part, sno, title in cases:
    row = pitha[(pitha['assembly_part_2025'] == part) & (pitha['booth_sno_2025'] == sno)].iloc[0]
    print(f'{title} -> Voter: \"{row.voter_name_en}\" | Rel: \"{row.rel_name_en}\" | Door: \"{row.door_no}\" | Group: {row.linguistic_group}')
