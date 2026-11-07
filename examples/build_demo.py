"""Generate fictional reports by executing the real engine; no network activity."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_pipeline import ready
from activity_pipeline import report, save

for mode in ('weekend', 'signup'):
    run, graph = ready(mode)
    save(ROOT / 'examples' / f'{mode}-run.json', run)
    (ROOT / 'examples' / f'{mode}-report.md').write_text(report(run, graph), encoding='utf-8')
