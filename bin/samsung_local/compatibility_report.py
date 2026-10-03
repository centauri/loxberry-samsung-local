"""Bounded developer evidence from reads already performed by the worker.

The summary exposes structure; the community export retains redacted values.
This collector performs no additional requests or security-resource reads.
"""

import re

from . import __version__
from .capabilities import normalize, readable
from .community import capture, envelope

P = 'x.com.samsung.da.'
PRIVATE = re.compile(r'uuid|serial|ssid|macaddress|password|credential|token|secret|owner|account|duid|certificate|privatekey', re.I)
IDENTIFIER = re.compile(r'[0-9a-f]{8}-[0-9a-f-]{27}|(?:\d{1,3}\.){3}\d{1,3}|(?:[0-9a-f]{2}:){5}[0-9a-f]{2}|[0-9a-f]{24,}', re.I)
BLOCKED = {'sec', 'security', 'ownership', 'wirelessinfo', 'configuration', 'file',
           'CoapCloudConfResURI', 'WiFiConfResURI', 'EasySetupResURI', 'DevConfResURI'}


def public_name(value, path=False):
    if not isinstance(value, str) or len(value) > 180 or PRIVATE.search(value):
        return None
    value = IDENTIFIER.sub('REDACTED', value)
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', value):
        return None
    if path and (not value.startswith('/') or any(p in BLOCKED for p in value.split('/'))):
        return None
    return value


def structure(value, depth=0):
    if depth >= 4:
        return {'type': 'truncated'}
    if isinstance(value, dict):
        return {'type': 'object', 'fields': {name: structure(v, depth + 1)
                for k, v in list(value.items())[:48] if (name := public_name(k))}}
    if isinstance(value, list):
        return {'type': 'array', 'items': [structure(v, depth + 1) for v in value[:3]]}
    return {'type': 'boolean' if isinstance(value, bool) else 'number' if isinstance(value, (int, float))
            else 'string' if isinstance(value, str) else 'null' if value is None else 'binary'}


def identity_text(value):
    if not isinstance(value, str):
        return None
    value = value.split('|', 1)[0][:100]
    if IDENTIFIER.search(value) or not re.fullmatch(r'[A-Za-z0-9_./() +:-]{1,100}', value):
        return None
    return value


def evidence(device, directory, batch, info, kind, reads):
    rows = {}
    def walk(node, depth=0):
        if depth > 8 or len(rows) >= 128:
            return
        if isinstance(node, list):
            for item in node[:256]:
                walk(item, depth + 1)
        elif isinstance(node, dict):
            raw = node.get('href')
            href = public_name(raw, path=True)
            if href:
                row = rows.setdefault(href, {'href': href, 'mapped_path': bool(readable(raw))})
                types = node.get('rt')
                if types is None and isinstance(node.get('rep'), dict):
                    types = node['rep'].get('rt')
                if isinstance(types, list):
                    row['resource_types'] = [n for t in types[:16] if (n := public_name(t))]
                rep = node.get('rep')
                if isinstance(rep, dict):
                    row['representation'] = structure(rep)
                    # Numeric/bool samples from known mappings only. Unknown
                    # strings, descriptions and arbitrary payloads stay redacted.
                    state, _ = normalize({raw: rep}, kind) if readable(raw) else ({}, {})
                    row['numeric_samples'] = {n: v for k, v in state.items()
                                              if isinstance(v, (int, float)) and (n := public_name(k))}
                    row['mapped_sensor_count'] = len(state)
            for key in ('links',):
                walk(node.get(key), depth + 1)
    walk(directory)
    walk(batch)
    metadata = {}
    for target, source in (('model', device.get('mnmo')), ('firmware', device.get('mnfv')),
                           ('board_family', info.get(P + 'modelNum'))):
        if (text := identity_text(source)):
            metadata[target] = text
    items = info.get(P + 'items', [])
    if 'firmware' not in metadata and isinstance(items, list):
        for item in items[:16]:
            if isinstance(item, dict) and item.get(P + 'type') == 'Software':
                if (text := identity_text(item.get(P + 'number'))):
                    metadata['firmware'] = text
                    break
    return {'community': capture(device, batch, info, kind),
            'identity': metadata, 'resources': list(rows.values()),
            'responses': {p: {'code': r.get('code')} for k, r in list(reads.items())[:128]
                          if (p := public_name(k, path=True))},
            'collection_limit': 128,
            'scope': 'Existing reads only; unadvertised or inaccessible resources may be absent. Unknown values are omitted.'}


def report(device):
    kind = device.get('kind', 'unknown')
    media = kind in {'television', 'network_audio'}
    community = device.get('compatibility_evidence', {}).get('community', {})
    result = {'format': 'samsung-local-compatibility-v2', 'plugin_version': __version__,
            'type': device.get('kind', 'unknown'), 'status': device.get('status', 'unknown'),
            'connection': device.get('connection_report', {'stage': 'not_attempted', 'error': None}),
            'evidence': device.get('compatibility_evidence', {}),
            'review_before_sharing': 'Contains redacted resource values, including unknown fields and appliance state. Review before attaching to a public issue. No automatic upload.',
            'limitations': 'Discovery does not prove authentication. A missing resource does not prove the device lacks it.'}
    result.update(envelope(community or {'device_type': kind}))
    result['discovery'] = {
        'device_types': [n for t in device.get('rt', [])[:32] if (n := public_name(t))],
        'samsung_detected': bool(device.get('samsung')),
        'source': 'Local discovery metadata; not authenticated appliance evidence.',
        'friendly_name': 'Omitted: user-editable names may contain personal information.',
        'retail_model': 'Not inferred from the friendly name. Supply the label model in your issue.',
    }
    result['collection'] = {
        'resource_capture': 'available' if community.get('resources') else 'unavailable',
        'reason': ('TV/audio profile is outside this adapter appliance implementation. '
                   'No appliance authentication or resource collection was attempted by this profile. '
                   'This does not establish whether another TV integration can support it.') if media else
                  ('Only resources already read by the adapter are included. '
                   'No capture may mean connection was not attempted, failed, or returned no resources.'),
    }
    result['support'] = {
        'route': 'adapter_scope' if media else 'capability_or_adapter_triage',
        'next_step': ('Ask in the adapter repository about TV integration scope; include the retail model. '
                      'This discovery-only report is not an appliance capability dump for LocalThings.') if media else
                     ('Search LocalThings issues for shared capability gaps. If already supported there, '
                      'report in the adapter repository. Include the retail model and expected behavior.'),
    }
    result['evidence'] = {k: v for k, v in result['evidence'].items() if k != 'community'}
    if media and device.get('media_inventory'):
        result['media_inventory'] = device['media_inventory']
        result['collection']['reason'] = ('Public TV/audio identification and advertised resource metadata were requested. '
                                          'No protected resource read or TV pairing was attempted. Advertisements do not prove access.')
        result['support']['next_step'] = ('For OCF VD research, compare this public inventory with '
                                        'QuiteYellow/SmartThings-Local docs/ocf-vd-devices.md. '
                                        'TV remote control requires a separate pairing integration, not appliance mappings.')
    return result
