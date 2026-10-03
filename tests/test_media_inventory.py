import json
from types import SimpleNamespace

import cbor2

from samsung_local import media_inventory
from samsung_local.compatibility_report import report


def test_public_inventory_keeps_metadata_without_private_identity(monkeypatch):
    calls = []
    def read(host, path, **kwargs):
        calls.append(path)
        body = {'mnmo': 'QE65Q90R', 'mnfv': 'T-TEST-1234', 'n': 'Private room', 'di': 'secret'} if path == '/oic/d' else {
            'links': [{'href': '/sec/tv/deviceinfo', 'rt': ['x.com.samsung.tv.deviceinfo'],
                       'eps': [{'ep': 'coaps://192.168.1.115:45955'}], 'rep': {'token': 'secret'}}]}
        return SimpleNamespace(code=69, payload=cbor2.dumps(body))
    monkeypatch.setattr(media_inventory, 'read_plaintext_ocf_resource', read)
    data = media_inventory.inventory('192.168.1.115', 5683)
    assert calls == ['/oic/d', '/oic/res']
    assert data['identity']['mnmo'] == 'QE65Q90R'
    assert data['resources'][0]['href'] == '/sec/tv/deviceinfo'
    assert not data['authenticated']
    assert 'secret' not in json.dumps(data) and '192.168' not in json.dumps(data)
    exported = report({'kind': 'television', 'media_inventory': data})
    assert exported['collection']['resource_capture'] == 'unavailable'
    assert exported['media_inventory']['protected_access'] == 'not_tested'


def test_failed_public_reads_do_not_invent_identity(monkeypatch):
    monkeypatch.setattr(media_inventory, 'read_plaintext_ocf_resource',
                        lambda *a, **k: SimpleNamespace(code=129, payload=b''))
    data = media_inventory.inventory('192.168.1.115', 5683)
    assert not data['identity'] and not data['resources']
    assert data['responses']['/oic/d'] == '4.01'
