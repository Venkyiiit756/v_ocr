"""
Command Line Interface for the Scalable Electoral Engine.
Usage example:
    python -m electoral_engine.cli \
        --ground-truth "C:/path/to/ward_voters.csv" \
        --rolls 168="path/168.pdf" 169="path/169.pdf" \
        --output "C:/path/to/deliverables" \
        --name "Machilipatnam_Ward_36_Master"
"""

import argparse
import sys
from .engine import ElectoralPipelineEngine

def main():
    parser = argparse.ArgumentParser(description="Scalable Electoral Roll Extraction & Master Directory Generator")
    parser.add_argument("--ground-truth", required=True, help="Path to official municipal/ward voters CSV/Excel")
    parser.add_argument("--rolls", nargs="+", required=True, help="List of Part=Path mappings (e.g. 168=part168.pdf 169=part169.pdf)")
    parser.add_argument("--output", required=True, help="Output directory for generated CSV and Excel")
    parser.add_argument("--name", default="Master_Voter_Directory", help="Base filename for outputs")
    parser.add_argument("--workers", type=int, default=6, help="Number of concurrent worker threads")

    args = parser.parse_args()

    # Parse rolls mapping
    pdf_mapping = {}
    for r in args.rolls:
        if "=" in r:
            part_str, path = r.split("=", 1)
            try:
                pdf_mapping[int(part_str)] = path
            except ValueError:
                pdf_mapping[part_str] = path
        else:
            print(f"Error: Roll mapping must be in PART=PATH format, got '{r}'")
            sys.exit(1)

    engine = ElectoralPipelineEngine(workers=args.workers)
    engine.run_pipeline(
        ground_truth_csv=args.ground_truth,
        pdf_mapping=pdf_mapping,
        output_dir=args.output,
        file_prefix=args.name
    )

if __name__ == "__main__":
    main()
