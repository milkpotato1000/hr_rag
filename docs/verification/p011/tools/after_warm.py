import time,subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011'
end=time.monotonic()+7200
while len(list((ev/'runs').glob('warm-*.json')))<120:
 if time.monotonic()>end:raise RuntimeError('warm run completion timeout; not launching cold')
 time.sleep(5)
assert len(list((ev/'runs').glob('warm-*.json')))==120
subprocess.run([sys.executable,str(Path(__file__).with_name('benchmark.py')),'cold'],check=True,cwd=root)
