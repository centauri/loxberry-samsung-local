"""Explicit dryer writes following upstream mqtt_demo/samples/dryer.py.

Only protocol mappings are reproduced; no resource paths come from callers.
Smart Control and child-lock checks are deliberately required for every write.
"""
from .capabilities import PREFIX, normalize

ACTIONS = {'start': 'Run', 'pause': 'Pause', 'stop': 'Ready',
           'wrinkle_on': 'On', 'wrinkle_off': 'Off'}


def available(kind, resources):
    return (kind == 'dryer'
            and resources.get('/operational/state/vs/0', {}).get(PREFIX + 'state')
            in {'Ready', 'Run', 'Running', 'Pause', 'Paused', 'End'})


def command(kind, resources, action):
    if action not in ACTIONS or not available(kind, resources):
        raise ValueError('Unsupported dryer command or resources')
    state, _ = normalize(resources, kind)
    if state.get('child_lock') is None and resources.get('/kidslock/vs/0', {}).get(PREFIX + 'kidsLock') == 'Ready':
        state['child_lock'] = 0  # Upstream dryer descriptor's unlocked representation.
    if state.get('remote_control') != 1 or state.get('child_lock') != 0:
        raise ValueError('Smart Control must be on and child lock must be off')
    if state.get('power') != 1:
        raise ValueError('Dryer must be powered on')
    current = resources['/operational/state/vs/0'][PREFIX + 'state']
    permitted = {'start': {'Ready', 'Pause', 'Paused'},
                 'pause': {'Run', 'Running'}, 'stop': {'Run', 'Running', 'Pause', 'Paused'}}
    if action in permitted:
        if current not in permitted[action]:
            raise ValueError('Command does not match the current dryer state')
        return '/operational/state/vs/0', {PREFIX + 'state': ACTIONS[action]}
    if resources.get('/washer/vs/0', {}).get(PREFIX + 'wrinklePrevent') not in {'On', 'Off'}:
        raise ValueError('Wrinkle prevention is not supported')
    return '/washer/vs/0', {PREFIX + 'wrinklePrevent': ACTIONS[action]}
