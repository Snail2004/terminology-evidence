from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
from review_workflow_v1_4.stage_a import finalize_sense_contract
parser = argparse.ArgumentParser()
parser.add_argument('workflow_root', type=Path)
parser.add_argument('--pilot-root', type=Path, required=True)
parser.add_argument('--output-root', type=Path, required=True)
parser.add_argument('--completed-at', required=True)
args = parser.parse_args()
result = finalize_sense_contract(args.workflow_root, args.pilot_root, args.output_root, completed_at=args.completed_at)

print(json.dumps(result, ensure_ascii=False, indent=2))
if isinstance(result, dict) and result.get('status') == 'FAIL':
    raise SystemExit(1)
