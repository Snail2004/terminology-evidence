from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
from review_workflow_v1_4.stage_b import generate_stage_b
parser = argparse.ArgumentParser()
parser.add_argument('--pilot-root', type=Path, required=True)
parser.add_argument('--sense-contract-root', type=Path, required=True)
parser.add_argument('--output-root', type=Path, required=True)
args = parser.parse_args()
result = generate_stage_b(args.pilot_root, args.sense_contract_root, args.output_root)

print(json.dumps(result, ensure_ascii=False, indent=2))
if isinstance(result, dict) and result.get('status') == 'FAIL':
    raise SystemExit(1)
