#pylint: disable-all
import time
import argparse
import multiprocessing
import os
import threading
import subprocess
import unittest
import traceback

DEVNULL = open(os.devnull, 'wb')


def iter_not_string(i):
  return hasattr(i, '__iter__')


def distribute_system_command(nprocesses, timeout, *cmds):
  '''Runs a series of system processes using 'nprocesses' workers and returns
  their collected return codes in the same order .'''
  count = max(map(lambda l: len(l) if iter_not_string(l) else 1, cmds))
  params = zip(*[c if iter_not_string(c) else ([c] * count) for c in cmds])
  queue = zip(range(count), params)
  total_task_count = count
  queue_lock = threading.Lock()
  results = []
  results_lock = threading.Lock()
  start_time = time.time()
  def task():
    '''Represents the task that a process controller thread has to perform.'''
    while len(queue) > 0:
      item = None
      with queue_lock:
        if len(queue) > 0:
          item = queue.pop()

      if item is not None:
        id, param = item
        task_start_time = time.time()
        r = subprocess.Popen(param, stdout=DEVNULL, stderr=subprocess.STDOUT)
        while r.poll() == None and time.time() - task_start_time < timeout:
          time.sleep(5)
        if r.poll() == None:
          r.terminate()
          print 'Task timed-out'
        with results_lock:
          results.append((id, r))
          time_elapsed = time.time() - start_time
          avg_time = time_elapsed / len(results)
          tasks_done = len(results)
          projected_time = avg_time * (total_task_count - tasks_done) / 60
          print '{0}/{1} tasks complete. Approx time left: {2:.2f} min'.\
                  format(tasks_done, total_task_count, projected_time)
  threads = []
  for i in range(nprocesses):
    thread = threading.Thread(target=task)
    threads.append(thread)
    thread.start()
  for t in threads:
    t.join()
  return map(lambda r: r[1], sorted(results, key=lambda r: r[0]))


class InterruptibleThreadGroup(threading.Thread):
  '''This class allows a user to run a list of tasks in different threads,
  and respond to requests for stoping, such as due to timeouts.'''

  def __init__(self, tasks):
    threading.Thread(self, name='Controller')
    self.threads = []
    for task in tasks:
      thread = threading.Thread(target=task)
      thread.daemon = True
      self.threads.append(thread)
    self.is_running = False
    self.running_status_lock = threading.Lock()
    self.running_status_changed = threading.Condition(self.running_status_lock)

  def run(self):
    '''Start the daemon threads and wait for a signal to stop.'''
    for t in self.threads:
      t.start()
    with self.running_status_lock:
      self.is_running = True
      while self.is_running:
        self.running_status_changed.wait()

  def stop_all_tasks(self):
    '''Signals the controlling thread to stop. Provided that the controlling
    thread is the only non-daemon thread, stopping it should force all the
    daemon task threads to die as well.'''
    with self.running_status_lock:
      self.is_running = False
      self.running_status_changed.notify_all()

  def wait_for_timeout(self, timeout_in_seconds):
    '''This function causes the calling thread to sleep for the given timeout
    and then call stop_all_tasks.'''
    start_time = time.time()
    while time.time() - start_time < timeout_in_seconds:
      thread.sleep(timeout_in_seconds - (time.time() - start_time))
    self.stop_all_tasks()

  @classmethod
  def run_tasks_until_timeout(cls, tasks, timeout):
    '''This class takes in a list of tasks and runs them up to timeout
    seconds.'''
    tg = cls(task)
    tg.start()
    tg.wait_for_timeout(timeout)


class SynchronizedTestResult(unittest.TestResult):
  def __init__(self):
    unittest.TextTestRunner.__init__(self)
    self.lock = threading.Lock()

  def addError(self, test, err):
    with self.lock:
      self.errors.append((test, traceback.format_exc(err)))

  def addFailure(self, test, err):
    with self.lock:
      self.failures.append((test, traceback.format_exc(err)))

  def addSuccess(self, test):
    pass

  def addSkip(self, test, reason):
    with self.lock:
      self.skipped.append((test, reason))

  def addExpectedFailure(self, test, err):
    with self.lock:
      self.expectedFailures.append((test, err))

  def addUnexpectedSuccess(self, test):
    with self.lock:
      self.unexpectedSuccesses.append(test)


class TimeoutTestRunner(object):
  def __init__(self, timeout):
    self.timeout = timeout

  def run(self, test_entity):
    task_list = []
    result = SynchronizedTestResult()
    if iter_not_string(test_entity):
      for test in test_entity:
        task_list.append(lambda: test.run(result))
    else:
      task_list.append(lambda: test_entity.run(result))
    InterruptibleThreadGroup.run_tasks_until_timeout(task_list, self.timeout)
    return result

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='This script is used to run ' +
    'several tests at once. The tests must be designed to follow the ' +
    'pattern described in the README.md')

  parser.add_argument('module', help='The module containing tests to be run.')

  parser.add_argument('batch_test_root', help='The directory containing ' +
    'subdirectories, each of which contain an instance of the modules to be ' +
    'tested.')

  parser.add_argument('-r', '--result_file_path', help='The path to the file, '+
    'relative to the directory containing the test modules, to store the ' + 
    'results as JSON objects.', default='results.json')

  parser.add_argument('-t', '--timeout', help='The max number of seconds a ' +
    'test is allowed to run.', default=600, type=float)

  args = parser.parse_args()
   
  for group in os.listdir(args.batch_test_root):
    instance_root = os.path.join(args.batch_test_root, group)
    if os.path.isdir(instance_root):
      sys.path.append(instance_root)
      m = __import__(args.module)
      reload(m)
      tests = unittest.defaultTestLoader.loadTestsFromModule(m)
      t = TimeoutTestRunner(args.timeout)
      sys.path.remove(instance_root)

  process_count = 2 * multiprocessing.cpu_count()

  if args.additional_arguments:
    res = distribute_system_command(process_count, float(args.timeout),'python',
        args.executable, solution_dirs, result_files,*args.additional_arguments)
  else:
    res = distribute_system_command(process_count, float(args.timeout),'python',
        args.executable, solution_dirs, result_files)

# vim: set ts=2 sw=2 expandtab:
