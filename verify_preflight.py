import importlib.util
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('preflight', 'lab-data-organizer/scripts/preflight.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def codes(path, methods):
    return {x['code'] for x in m.audit(path, methods)['issues']}

with tempfile.TemporaryDirectory(dir=Path.cwd(), prefix='preflight-test-') as d:
    r = Path(d)
    methods = r / 'methods'
    key = methods / 'UV-Vis_ModelA_Scan'
    key.mkdir(parents=True)
    (key / 'METHOD.md').write_text('test fixture')
    leaf = r / '20261031' / 'B - Test' / key.name / 'OD'
    leaf.mkdir(parents=True)
    stem = '20261031-B-UV-Vis-OD'
    (leaf / (stem + '.txt')).write_text('description')
    (leaf / 'raw.xlsx').write_bytes(b'fixture')
    result = m.audit(leaf, methods)
    assert not result['issues'], result
    assert result['tasks'][0]['raw_candidates'] == ['raw.xlsx']
    assert result['processing_authorized'] is False
    (leaf / (stem + '.xlsx')).write_bytes(b'fixture')
    assert 'OUTPUT_EXISTS' in codes(leaf, methods)
    (leaf / (stem + '.txt')).unlink()
    assert 'DESCRIPTION_MISSING' in codes(leaf, methods)
    other = r / '20261031' / 'C - CaseTest' / 'uv-vis_ModelA_Scan' / 'OD'
    other.mkdir(parents=True)
    assert 'UNKNOWN_INSTRUMENT' in codes(r / '20261031', methods)
    bad = r / '261031' / 'B - Test'
    bad.mkdir(parents=True)
    assert 'DATE_FORMAT' in codes(bad.parent, methods)
    for start in [leaf.parent, leaf.parent.parent, leaf.parent.parent.parent]:
        assert m.audit(start, methods)['tasks']
    assert 'UNKNOWN_INSTRUMENT' in codes(r / '20261031', r / 'empty-methods')
    assert 'UNKNOWN_INSTRUMENT' in codes(leaf, r / 'empty-methods')
print('PASS: ancestor scanning, raw XLSX preservation, collision, missing description, exact instrument match, dates, empty methods, no processing authorization')
