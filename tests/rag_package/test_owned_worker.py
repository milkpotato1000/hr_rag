"""Independent direct-process monitoring and pipe/cancellation tests (P032 S1)."""
import os,sys,threading,time,unittest
from unittest.mock import patch
from rag_package.owned_worker import communicate_owned,execution_scope
from rag_package.storage import RagError

class OwnedTests(unittest.TestCase):
 def run_child(self,code,*,timeout=3,monitor=None,rss_reader=None,cancel=None,text='x'):
  self.obs={}
  return communicate_owned([sys.executable,'-c',code],text,timeout,env={'PATH':os.defpath},observation=self.obs,monitor=monitor or (lambda:{'pressure':'normal'}),rss_reader=rss_reader or (lambda _:1024),cancel=cancel)
 def test_normal_and_large_pipes(self):
  code="import sys,time; sys.stdout.write('a'*2000000);sys.stdout.flush();sys.stderr.write('b'*2000000);sys.stderr.flush();x=sys.stdin.read();time.sleep(.3);print(x)"
  out,err,rc=self.run_child(code,text='c'*2000000)
  self.assertEqual(rc,0);self.assertEqual(len(err),2000000);self.assertEqual(len(out),4000001)
  self.assertTrue(self.obs['worker_exited'] and self.obs['resume_safe']);self.assertTrue(self.obs['samples'])
  self.assertGreater(self.obs['sampling_max_gap_ms'],0)
 def test_timeout_owned_process_reaped(self):
  with self.assertRaisesRegex(RagError,'worker_timeout'):self.run_child('import time;time.sleep(30)',timeout=.15)
  self.assertTrue(self.obs['worker_exited']);self.assertTrue(self.obs['io_thread_exited']);self.assertFalse(self.obs['completed'])
 def test_pressure_limit_measurement_failure_and_nonzero(self):
  for reason in ('memory_pressure','worker_rss_limit','rss_observation_unavailable'):
   seen=[0]
   def monitor():
    seen[0]+=1
    if reason=='memory_pressure' and seen[0]>1:raise RagError(reason,'test')
    return {'pressure':'normal'}
   def resident(_):
    if reason=='rss_observation_unavailable':raise RagError(reason,'test')
    return 4*1024**3 if reason=='worker_rss_limit' else 1
   with self.subTest(reason=reason),self.assertRaisesRegex(RagError,reason):self.run_child('import time;time.sleep(30)',monitor=monitor,rss_reader=resident)
   self.assertTrue(self.obs['worker_exited'] and self.obs['io_thread_exited'])
  _,_,rc=self.run_child('raise SystemExit(7)');self.assertEqual(rc,7);self.assertFalse(self.obs['completed']);self.assertTrue(self.obs['worker_exited'])
 def test_preflight_cancel_and_interrupt_after_spawn(self):
  with self.assertRaisesRegex(RagError,'unavailable'):self.run_child('pass',monitor=lambda:(_ for _ in ()).throw(RagError('unavailable','test')))
  self.assertEqual(self.obs['workers_started'],0)
  cancelled=threading.Event();cancelled.set()
  with self.assertRaisesRegex(RagError,'worker_cancelled'):self.run_child('pass',cancel=cancelled)
  self.assertEqual(self.obs['workers_started'],0)
  cancelled.clear();timer=threading.Timer(.1,cancelled.set);timer.start()
  try:
   with self.assertRaisesRegex(RagError,'worker_cancelled'):self.run_child('import time;time.sleep(30)',cancel=cancelled)
   self.assertTrue(self.obs['worker_exited'] and self.obs['io_thread_exited'])
  finally:timer.join()
  for error in (KeyboardInterrupt,SystemExit):
   seen=[0]
   def monitor():
    seen[0]+=1
    if seen[0]>1:raise error()
    return {'pressure':'normal'}
   with self.assertRaises(error):self.run_child('import time;time.sleep(30)',monitor=monitor)
   self.assertTrue(self.obs['worker_exited'] and self.obs['io_thread_exited'])
 def test_measurement_latency_counts_toward_timeout(self):
  def monitor():time.sleep(.12);return {'pressure':'normal'}
  with self.assertRaisesRegex(RagError,'worker_timeout'):self.run_child('pass',timeout=.1,monitor=monitor)
  self.assertEqual(self.obs['workers_started'],0)
 def test_scope_deadline_and_durable_before_spawn(self):
  events=[]
  class Control:
   def __init__(self):self.end=time.monotonic()+.2
   def check(self):
    if time.monotonic()>=self.end:raise RagError('overall_deadline','test')
   def before_spawn(self,cmd):events.append('intent')
   def after_worker(self,obs):events.append(('done',obs['workers_started'],obs['worker_exited']))
  with execution_scope(Control()),self.assertRaisesRegex(RagError,'overall_deadline'):self.run_child('import time;time.sleep(30)')
  self.assertEqual(events,['intent',('done',1,True)])
  class Bad(Control):
   def before_spawn(self,cmd):raise OSError('journal denied')
  with execution_scope(Bad()),self.assertRaisesRegex(RagError,'worker_io_failed'):self.run_child('pass')
  self.assertEqual(self.obs['workers_started'],0)
 def test_delayed_pipe_error_after_child_exit(self):
  import subprocess
  release=threading.Event()
  class Process:
   returncode=None;pid=123
   def communicate(self,*args,**kwargs):
    release.wait(2);raise RagError('late_pipe_failure','test')
   def poll(self):return self.returncode
   def wait(self,**kw):return self.returncode
   def kill(self):self.returncode=-9;release.set()
  proc=Process()
  def resident(_):
   proc.returncode=0
   threading.Timer(.05,release.set).start()
   raise RagError('rss_observation_unavailable','test')
  with patch('rag_package.owned_worker.subprocess.Popen',return_value=proc),self.assertRaisesRegex(RagError,'late_pipe_failure'):
   self.run_child('pass',rss_reader=resident)
  self.assertTrue(self.obs['worker_exited'] and self.obs['io_thread_exited'])
 def test_recording_failure_preserves_original_execution(self):
  class Control:
   def check(self):pass
   def before_spawn(self,cmd):pass
   def after_worker(self,obs):raise OSError('record failed')
  with execution_scope(Control()),self.assertRaisesRegex(RagError,'worker_recording_failed') as cm:self.run_child('pass')
  self.assertTrue(cm.exception.observation['completed']);self.assertTrue(cm.exception.observation['worker_exited'])
  for error in (RagError('memory_pressure','test'),KeyboardInterrupt()):
   seen=[0]
   def monitor():
    seen[0]+=1
    if seen[0]>1:raise error
    return {'pressure':'normal'}
   with execution_scope(Control()),self.assertRaises(type(error)) as cm:self.run_child('import time;time.sleep(30)',monitor=monitor)
   self.assertIs(cm.exception,error);self.assertEqual(cm.exception.recording_error,'OSError');self.assertTrue(self.obs['worker_exited'])

 def test_scope_not_applied_to_unowned_process(self):
  import subprocess
  other=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
  try:
   with self.assertRaises(RagError):self.run_child('import time;time.sleep(30)',timeout=.1)
   self.assertIsNone(other.poll())
  finally:other.terminate();other.wait()

if __name__=='__main__':unittest.main()
