#!/usr/bin/env python3
"""Backfill Phase 1 outputs from already validated, committed normalized tables."""
import json
import shutil
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from wcbb_espn.refresh import read_parquet, PLAYER_FAMILY
from wcbb_espn.features import write_feature_bundle

def main():
    manifest=json.loads((ROOT/'reports/manifest_latest.json').read_text())
    assert manifest['status'] in ('PASS','PASS_WITH_REVIEW')
    players=read_parquet(ROOT/f'data/latest/{PLAYER_FAMILY}/player_season.parquet')
    skills=read_parquet(ROOT/f'data/latest/{PLAYER_FAMILY}/skill_impacts.parquet')
    (ROOT/'.staging').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT/'.staging') as temp:
        stage=Path(temp)/'processed'
        qa=write_feature_bundle(players,skills,ROOT,stage,manifest)
        snapshot=ROOT/f"data/processed/snapshots/{manifest['run_id']}"
        if snapshot.exists():
            raise RuntimeError('Processed snapshot already exists; use the normal refresh for a new revision')
        from wcbb_espn.publication import publication_transaction
        targets = [ROOT/'reports/manifest_latest.json']
        for base in [ROOT/'data/processed', snapshot]:
            targets.extend(base/p.relative_to(stage) for p in stage.rglob('*') if p.is_file())
        with publication_transaction(Path(temp), targets):
            shutil.copytree(stage,snapshot)
            output=ROOT/'data/processed'
            for child in stage.iterdir():
                if child.is_dir():shutil.copytree(child,output/child.name,dirs_exist_ok=True)
                else:shutil.copy2(child,output/child.name)
            manifest['processed_features']=qa
            if qa['status'] == 'PASS_WITH_REVIEW':
                manifest['status'] = 'PASS_WITH_REVIEW'
            manifest['processed_snapshot_path']=str(snapshot.relative_to(ROOT))
            (ROOT/'reports/manifest_latest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':qa['status'],'player_rows':qa['player_rows'],'skill_rows':qa['skill_rows']}))
if __name__=='__main__':main()
