"""Replay LocalThings diagnostics/fixtures or adapter reports offline.

JSON is evidence, never executable mapping code. Output is for maintainer review;
normal plugin updates deliver reviewed mapping/protocol fixes to appliances.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from samsung_local.capabilities import device_type, normalize, readable  # noqa: E402
from samsung_local.community import capture  # noqa: E402


def replay(document):
    if not isinstance(document, dict):
        raise ValueError('Expected a JSON object')
    data = document.get('data', document)
    if not isinstance(data, dict):
        raise ValueError('Expected diagnostics data object')
    resources = data.get('resources')
    if resources is None and isinstance(data.get('device0'), list):
        resources = {row['href']: row['rep'] for row in data['device0']
                     if isinstance(row, dict) and isinstance(row.get('href'), str)
                     and isinstance(row.get('rep'), dict)}
    if not isinstance(resources, dict) or len(resources) > 512:
        raise ValueError('Expected resources map or device0 fixture (maximum 512 resources)')
    identity = data.get('identity') or {}
    if not isinstance(identity, dict):
        raise ValueError('Expected identity object')
    rt = identity.get('device_types', data.get('rt', []))
    if not isinstance(rt, list) or not all(isinstance(t, str) for t in rt):
        raise ValueError('Expected device_types list')
    kind = device_type(rt, resources.get('/information/vs/0', {}))
    batch = [{'href': h, 'rep': r} for h, r in resources.items() if isinstance(r, dict)]
    sanitized = capture({'rt': rt}, batch, {}, kind)
    state, sensors = normalize({h: r for h, r in sanitized['resources'].items() if readable(h)}, kind)
    return {'device_type': kind, 'state': state, 'sensors': sensors,
            'unbound_hrefs': sanitized['unbound_hrefs'],
            'fixture': {'rt': rt, 'device0': [{'href': h, 'rep': r}
                        for h, r in sanitized['resources'].items()]},
            'limitations': 'Offline mapping only; no proof of authentication, hardware or write support. Composite subdevices are not replayed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.report.stat().st_size > 4 * 1024 * 1024:
        parser.error('Report exceeds 4 MiB')
    raw = args.report.read_bytes()
    try:
        result = replay(json.loads(raw))
    except (ValueError, TypeError, RecursionError) as exc:
        parser.error(str(exc))
    result['source_sha256'] = hashlib.sha256(raw).hexdigest()
    # Never overwrite an existing capture or expected-result file.
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=True, allow_nan=False)


if __name__ == '__main__':
    main()
