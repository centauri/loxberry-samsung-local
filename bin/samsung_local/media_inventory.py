"""Public VD-family inventory, following upstream ocf-vd-devices.md.

Only /oic/d and /oic/res GETs. No pairing, ownership, security or control writes.
Advertised secure links are metadata, not a claim of authorized access.
"""
import re

import cbor2
from smartthings_local.protocol.ocf_discovery import read_plaintext_ocf_resource


def safe_text(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./() -]{1,120}', value):
        return None
    if re.search(r'[0-9a-f]{8}-[0-9a-f-]{27}|(?:\d{1,3}\.){3}\d{1,3}|[0-9a-f]{24,}', value, re.I):
        return None
    return value


def inventory(host, port):
    result = {'source': 'public_ocf', 'responses': {}, 'identity': {}, 'resources': [],
              'authenticated': False, 'protected_access': 'not_tested'}
    for path in ('/oic/d', '/oic/res'):
        try:
            response = read_plaintext_ocf_resource(host, path, port=port, timeout=2, retries=0)
            result['responses'][path] = f'{response.code >> 5}.{response.code & 31:02d}'
            if response.code != 69 or len(response.payload) > 65536:
                continue
            body = cbor2.loads(response.payload)
            if path == '/oic/d' and isinstance(body, dict):
                for key in ('mnmo', 'mnfv', 'vid', 'mnos', 'mnpv'):
                    if value := safe_text(body.get(key)):
                        result['identity'][key] = value
            elif path == '/oic/res':
                def walk(node, depth=0):
                    if depth > 8 or len(result['resources']) >= 128:
                        return
                    if isinstance(node, list):
                        for item in node[:128]:
                            walk(item, depth + 1)
                    elif isinstance(node, dict):
                        href = safe_text(node.get('href'))
                        if href and href.startswith('/'):
                            row = {'href': href}
                            for key in ('rt', 'if'):
                                values = node.get(key)
                                if isinstance(values, list):
                                    row[key] = [text for v in values[:16] if (text := safe_text(v))]
                            result['resources'].append(row)
                        walk(node.get('links'), depth + 1)
                walk(body)
        except Exception as error:
            result['responses'][path] = type(error).__name__
    return result
