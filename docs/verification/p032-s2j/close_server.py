"""Release the exact server owned by this run after confirmed unload."""
import os
import signal
from runtime import *

def close():
    ownership_record = read(E / 'server-ownership.json')
    pid = ownership_record['pid']
    if not ownership_record['owned']:
        return {'owned': False, 'stopped': False}
    observed = read(E / 'w000-observation.json')
    need(observed['unloaded_observed'] and observed['client_reaped'], 'cleanup_unconfirmed')
    need(listener() == pid and sha(BINARY) == ownership_record['binary_sha256'], 'server_changed')
    matches = [r for r in ps() if r['pid'] == pid and Path(r['comm']) == BINARY]
    need(len(matches) == 1, 'process_identity_changed')
    os.kill(pid, signal.SIGTERM)
    for _ in range(40):
        if listener() is None:
            return {'owned': True, 'pid': pid, 'listener_closed': True}
        time.sleep(0.25)
    raise Stop('listener_still_open')

if __name__ == '__main__':
    write(E / 'server-closed.json', close())
