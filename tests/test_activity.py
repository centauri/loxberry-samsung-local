import logging

from samsung_local.activity import Activity, reference


def test_transitions_log_without_poll_spam_or_private_data(caplog):
    caplog.set_level(logging.INFO, logger='samsung_local.activity')
    monitor = Activity()
    registry = {'private-identifier': {'status': 'online', 'kind': 'dryer',
                'host': '192.168.1.49', 'name': 'private-name',
                'state': {'power': 1}, 'connection_report': {'stage': 'readings', 'error': None}}}
    monitor.observe(registry, True, True)
    assert 'untracked -> online' in caplog.text
    assert reference('private-identifier') in caplog.text
    assert 'private-name' not in caplog.text and '192.168.1.49' not in caplog.text
    assert 'private-identifier' not in caplog.text
    count = len(caplog.records)
    for _ in range(10):
        monitor.observe(registry, True, True)
    assert len(caplog.records) == count
    registry['private-identifier']['status'] = 'offline'
    registry['private-identifier']['connection_report'] = {'stage': 'authentication', 'error': 'SessionError'}
    monitor.observe(registry, False, True)
    assert 'online -> offline' in caplog.text and 'SessionError' in caplog.text
    assert 'MQTT disconnected' in caplog.text


def test_summary_interval_and_unknown_metadata_are_bounded(caplog):
    caplog.set_level(logging.INFO, logger='samsung_local.activity')
    monitor = Activity()
    monitor.summary_at = 0
    registry = {'test': {'status': 'unsupported', 'kind': 'private\nname',
                        'connection_report': {'error': 'secret\npassword'}}}
    monitor.observe(registry, True, True, now=899)
    assert 'Health summary' not in caplog.text
    monitor.observe(registry, True, True, now=900)
    assert caplog.text.count('Health summary') == 1
    monitor.observe(registry, True, True, now=901)
    assert caplog.text.count('Health summary') == 1
    assert 'secret' not in caplog.text and 'private' not in caplog.text
