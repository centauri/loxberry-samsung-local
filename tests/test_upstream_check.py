import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('upstream', Path(__file__).resolve().parents[1] / 'tools/check_upstream.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('changed', [False, True])
def test_read_only_check_uses_exact_head_and_relevant_paths(changed):
    old, head = 'a' * 40, ('b' if changed else 'a') * 40
    calls = []
    def fetch(path):
        calls.append(path)
        if '/compare/' in path:
            return {'status': 'ahead' if changed else 'identical', 'ahead_by': int(changed),
                    'files': [{'filename': 'tests/fixtures/new.json'}, {'filename': 'README.md'}] if changed else []}
        if '/commits/' in path:
            return {'sha': head}
        return {'default_branch': 'main'}
    row = module.check({'repository': 'owner/repo', 'reviewed_commit': old, 'paths': ['tests/fixtures/']}, fetch)
    assert row['changed'] is changed
    assert row['relevant_files'] == (['tests/fixtures/new.json'] if changed else [])
    assert calls[-1].endswith(old + '...' + head)
    assert 'no dependency' in module.markdown([row])


def test_invalid_baseline_rejected_before_network():
    with pytest.raises(ValueError):
        module.check({'repository': '../bad', 'reviewed_commit': 'main'}, lambda _: pytest.fail('network called'))
