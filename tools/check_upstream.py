"""Read-only upstream drift report. Never downloads or executes upstream code."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def get_json(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'loxberry-samsung-local-upstream-check',
               'X-GitHub-Api-Version': '2022-11-28'}
    if token := os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('https://api.github.com/' + path, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def check(source, fetch=get_json):
    repo, baseline = source['repository'], source['reviewed_commit']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or not re.fullmatch(r'[0-9a-f]{40}', baseline):
        raise ValueError('Invalid upstream reference')
    metadata = fetch('repos/' + repo)
    branch = metadata['default_branch']
    from urllib.parse import quote
    head = fetch(f'repos/{repo}/commits/{quote(branch, safe="")}')['sha']
    if not re.fullmatch(r'[0-9a-f]{40}', head):
        raise ValueError('Invalid upstream head')
    compared = fetch(f'repos/{repo}/compare/{baseline}...{head}')
    files = compared.get('files', [])
    relevant = [f['filename'] for f in files if any(f['filename'].startswith(p) for p in source['paths'])]
    return {'repository': repo, 'baseline': baseline, 'head': head,
            'changed': baseline != head, 'comparison': compared['status'],
            'ahead_by': compared.get('ahead_by', 0), 'relevant_files': relevant,
            'file_list_may_be_truncated': len(files) >= 300,
            'compare_url': f'https://github.com/{repo}/compare/{baseline}...{head}'}


def markdown(results):
    lines = ['# Upstream review', '', 'Detection only: no dependency, mapping or appliance changes were made.', '']
    for row in results:
        lines += [f"## {row['repository']}", '',
                  f"Reviewed: `{row['baseline']}`", f"Current: `{row['head']}`", '',
                  f"Comparison: {row['comparison']}; commits ahead: {row['ahead_by']}.",
                  f"[Review upstream diff]({row['compare_url']})", '',
                  'Relevant changed paths (a heuristic, not a compatibility assessment):', '']
        lines += ['- `' + p.replace('`', '').replace('\n', '') + '`' for p in row['relevant_files']]
        if not row['relevant_files']:
            lines += ['- None in the returned file list. Review the full comparison before dismissing changes.']
        if row['file_list_may_be_truncated']:
            lines += ['', 'GitHub may have truncated the file list; use the full comparison.']
        lines += ['']
    lines += ['Review changes and new fixtures, adapt mappings or dependency pins, run tests, and release an adapter update.',
              'Advance reviewed_commit only after documenting what was adopted or deliberately deferred.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/upstream')
    parser.add_argument('--fail-on-change', action='store_true')
    args = parser.parse_args()
    sources = json.loads((ROOT / 'tools/upstream.json').read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        results = [check(source) for source in sources]
    except (urllib.error.URLError, ValueError, KeyError, TimeoutError) as error:
        message = 'Upstream check failed; no freshness result is available. ' + type(error).__name__
        if isinstance(error, urllib.error.HTTPError):
            message += f' (HTTP {error.code})'
        (args.output / 'report.md').write_text(message + '\n', encoding='utf-8')
        print(message, file=sys.stderr)
        return 1
    body = markdown(results)
    (args.output / 'report.md').write_text(body, encoding='utf-8')
    (args.output / 'report.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write(body)
    print(body)
    return 2 if args.fail_on_change and any(r['changed'] for r in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
