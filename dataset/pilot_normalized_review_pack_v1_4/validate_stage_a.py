from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
from review_workflow_v1_4.stage_a import validate_stage_a
parser = argparse.ArgumentParser()
parser.add_argument('workflow_root', type=Path)
parser.add_argument('--pilot-root', type=Path, required=True)
parser.add_argument('--require-complete', action='store_true')
args = parser.parse_args()
result = validate_stage_a(args.workflow_root, args.pilot_root, require_complete=args.require_complete)

print(json.dumps(result, ensure_ascii=False, indent=2))
if isinstance(result, dict) and result.get('status') == 'FAIL':
    raise SystemExit(1)
