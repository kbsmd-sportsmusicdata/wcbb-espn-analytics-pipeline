#!/usr/bin/env python3
"""Run a QA-gated ESPN Analytics WCBB refresh for the 45-team cohort."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from wcbb_espn.refresh import refresh_repository


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--season",type=int,default=2026)
    args=ap.parse_args()
    report=refresh_repository(ROOT,args.season)
    print(json.dumps({"status":report["status"],"run_id":report["run_id"],
                      "qa": [{k:v for k,v in q.items() if k not in ("sources",)} for q in report["qa"]]},indent=2))

if __name__=="__main__":
    main()
