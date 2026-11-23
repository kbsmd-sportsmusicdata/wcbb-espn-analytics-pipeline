from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_scheduled_refresh_timezone_and_permissions():
    text=(ROOT/'.github/workflows/refresh_wcbb.yml').read_text()
    value=yaml.load(text,Loader=yaml.BaseLoader)
    assert value['on']['schedule'][0]['cron']=='15 9 * * 2,5'
    assert value['on']['schedule'][0]['timezone']=='America/Los_Angeles'
    assert value['permissions']['contents']=='write'
    assert 'workflow_dispatch' in value['on']


def test_template_pages_deployment_not_automatic():
    value=yaml.load((ROOT/'.github/workflows/deploy_pages.yml').read_text(),Loader=yaml.BaseLoader)
    assert 'push' not in value['on']
    assert 'schedule' not in value['on']


def test_cohort_belongs_to_reference_directory():
    assert (ROOT/'data/reference/cohort_45.csv').is_file()
    assert (ROOT/'reports/hex_45_team_validation_reference_2026-11-23.csv').is_file()
