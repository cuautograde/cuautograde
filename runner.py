import time
import argparse
import multiprocessing
import os
import threading
import subprocess
import unittest
import traceback
import random
import sys
import json
import functools
 

# Set the random seed so that the tests are consistent across all runs
random.seed(20150219)

# Preserve the original output stream
console = sys.stdout

# Protects the output stream
console_lock = threading.Lock()

# Send all prints and error prints to black hole
f = open(os.devnull, 'w')
sys.stdout = f
sys.stderr = f


def displayln(s):
  '''Write the string 's' to the original console output stream.'''
  with console_lock:
    console.write('{0}\n'.format(s))


def iter_not_string(i):
  return hasattr(i, '__iter__')


def list_of_tests_gen(s):
  '''A generator of tests from a suite.'''
  for test in s:
    if unittest.suite._isnotsuite(test):
      yield test
    else:
      for t in list_of_tests_gen(test):
        yield t


class InterruptibleThreadGroup(threading.Thread):
  '''This class allows a user to run a list of tasks in different threads,
  and respond to requests for stoping, such as due to timeouts.'''

  def __init__(self, tasks, args, finalizers=None):
    ''''tasks' is a list of single parameter functions corresponding to a
    single interruptible task to be performed by this thread group.
    'args' is a list (same size as 'tasks') of arguments corresponding to
    those expected by the respective task. 'finalizers' are single parameter
    functions called after the task, and receives the same parameter as the
    corresponding task.'''
    threading.Thread.__init__(self, name='Controller',
        target=self.start_and_wait)

    self.threads = []

    # When the count goes to zero, the thread group is shutdown
    self.tasks_running_count = len(tasks)

    # This lock protects the state of the thread group
    self.running_status_lock = threading.Lock()

    # This signals a change of the state of the thread group from running to
    # shutdown
    self.running_status_changed = threading.Condition(self.running_status_lock)

    # The running/not running state of the thread group
    self.is_running = False

    if finalizers is None:
      finalizers = [None] * len(tasks)

    for task, arg, finalizer in zip (tasks, args, finalizers):
      def unit_work(param):
        task(param)
        if finalizer is not None:
          finalizer(param)
        with self.running_status_lock:
          self.tasks_running_count -= 1
          if self.tasks_running_count == 0:
            self.is_running = False
            self.running_status_changed.notify_all()

      thread = threading.Thread(target=unit_work, args=(arg,))
      thread.daemon = True
      self.threads.append(thread)

  def start_and_wait(self):
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

  def set_timeout(self, timeout_in_seconds):
    def task():
      start_time = time.time()
      while time.time() - start_time < timeout_in_seconds:
        time.sleep(timeout_in_seconds - (time.time() - start_time))
      self.stop_all_tasks()
    thread = threading.Thread(target=task)
    thread.daemon = True
    thread.start()

  @classmethod
  def run_tasks_until_timeout(cls, tasks, args, finalizers, timeout):
    '''This class takes in a list of tasks and runs them up to timeout
    seconds.'''
    tg = cls(tasks, args, finalizers)
    tg.start()
    tg.set_timeout(timeout)
    tg.join()


class SynchronizedTestResult(unittest.TestResult):
  def __init__(self):
    unittest.TestResult.__init__(self)
    self.lock = threading.Lock()
    self.frozen = False
    self.successes = []

  def addError(self, test, err):
    with self.lock:
      if not self.frozen:
        self.errors.append((test, traceback.format_exc(err)))

  def addFailure(self, test, err):
    with self.lock:
      if not self.frozen:
        self.failures.append((test, traceback.format_exc(err)))

  def addSuccess(self, test):
    with self.lock:
      if not self.frozen:
        self.successes.append(test)

  def addSkip(self, test, reason):
    with self.lock:
      if not self.frozen:
        self.skipped.append((test, reason))

  def addExpectedFailure(self, test, err):
    with self.lock:
      if not self.frozen:
        self.expectedFailures.append((test, err))

  def addUnexpectedSuccess(self, test):
    with self.lock:
      if not self.frozen:
        self.unexpectedSuccesses.append(test)

  def freeze(self):
    with self.lock:
      self.frozen = True

  def getStatusAsString(self, test):
    assert test != None
    mod_name, class_name, func_name = test.id().split('.')
    if len(self.errors) > 0 and test in zip(*self.errors)[0]:
      return 'Completed with error: {0}'.format(func_name)
    elif len(self.failures) > 0 and test in zip(*self.failures)[0]:
      return 'Completed with failure: {0}'.format(func_name)
    elif len(self.successes) > 0 and test in self.successes:
      return 'Completed with success: {0}'.format(func_name)
    elif len(self.skipped) > 0 and test in zip(*self.skipped)[0]:
      return 'Skipped: {0}'.format(func_name)
    elif len(self.expectedFailures) > 0 and \
        test in zip(*self.expectedFailures)[0]:
      return 'Completed with expected failure: {0}'.format(func_name)
    elif len(self.unexpectedSuccesses) > 0 and test in self.unexpectedSuccesses:
      return 'Completed with unexpected success: {0}'.format(func_name)
    else:
      return 'Not completed: {0}'.format(func_name)

  def summarize(self, all_tests):
    all_tests = list(list_of_tests_gen(all_tests))
    s = {
      'errors': {k.id(): v for k, v in self.errors},
      'failures': {k.id(): v for k, v in self.failures},
      'successes': [t.id() for t in self.successes],
      'skipped': {k.id(): v for k, v in self.skipped},
      'expectedFailures': {k.id(): v for k, v in self.expectedFailures},
      'unexpectedSuccesses': [t.id() for t in self.unexpectedSuccesses],
      'allTests': [t.id() for t in all_tests]
    }
    processed_union = set().union(s['errors'].keys(), s['failures'].keys(),
        s['successes'], s['skipped'].keys(), s['expectedFailures'].keys(),
        s['unexpectedSuccesses'])
    s['aborted'] = list(set(x.id() for x in all_tests) - processed_union)
    return s
          

class TimeoutTestRunner(object):
  def __init__(self, timeout):
    self.timeout = timeout

  @staticmethod
  def process_test_cases(entity, func_name, already_processed=set()):
    '''Runs the specific function of every TestCase object encountered,
    recusively starting at root.'''
    if isinstance(entity, unittest.TestSuite):
      for t in entity:
        if isinstance(t, unittest.TestCase):
          if not t.__class__ in already_processed:
            getattr(t.__class__, func_name)()
            already_processed.add(t.__class__)
        else:
          TimeoutTestRunner.process_test_cases(t, func_name, already_processed)
    else:
      raise Exception('Unknow object encountered in the TestSuite!')

  def run(self, test_entity, verbose=False):
    result = SynchronizedTestResult()
    TimeoutTestRunner.process_test_cases(test_entity, 'setUpClass')
    tests = list(list_of_tests_gen(test_entity))
    test_tasks = [lambda t: t.run(result)] * len(tests)
    disp_tasks = [lambda t: displayln(result.getStatusAsString(t))] * len(tests)
    if not verbose:
      disp_tasks = None
    InterruptibleThreadGroup.run_tasks_until_timeout(test_tasks, tests,
        disp_tasks, self.timeout)
    result.freeze()
    TimeoutTestRunner.process_test_cases(test_entity, 'tearDownClass')
    return result


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='This script is used to run ' +
    'a single tests at a time. The tests must be designed to follow the ' +
    'pattern described in the README.md',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument('module', help='The module containing tests to be run.')

  parser.add_argument('test_root', help='The directory containing the modules '+
    'to be tested.')

  parser.add_argument('-r', '--result_file_path', help='The path to the file, '+
    'relative to test_root, to store the results as JSON objects.',
    default='results.json')

  parser.add_argument('-t', '--timeout', help='The max number of seconds a ' +
    'test is allowed to run.', default=600, type=float)

  parser.add_argument('-o', '--overwrite_existing_results', help='Indicates ' +
    'what action to take when a result file already exists',
    action='store_true', default=False)

  parser.add_argument('-v', '--verbose', help='Show the result of every test.',
    action='store_true', default=False)

  args = parser.parse_args()

  # First check if the result file exists
  result_file_path = os.path.join(args.test_root, args.result_file_path)
  basename = os.path.basename(os.path.abspath(args.test_root))
  if os.path.isfile(result_file_path) and not args.overwrite_existing_results:
    displayln('Results already exist for {0}'.format(basename))
    exit(1)

  # A hack to make symlinks work
  sys.path.append(os.getcwd())
  if os.path.isdir(args.test_root):
    sys.path.append(args.test_root)
    m = __import__(args.module)
    tests = unittest.defaultTestLoader.loadTestsFromModule(m)
    result = TimeoutTestRunner(args.timeout).run(tests, args.verbose)
    summary = result.summarize(tests)

    with open(result_file_path, 'w') as result_file:
      json.dump(summary, result_file, indent=True)


    # Display a summary of the students' results to let the test runner know
    # the test runner is making progress
    # pylint: disable=E1601
    displayln(('{0}: Successful={1}/{6}, Errors={2}/{6}, Failed={3}/{6}, ' + 
      'Aborted={4}/{6}, Skipped={5}/{6}').format(basename,
      len(summary['successes']), len(summary['errors']),
      len(summary['failures']), len(summary['aborted']),
      len(summary['skipped']), len(summary['allTests'])))
    
    if len(summary['aborted']) > 0:
      exit(2)
  else:
    raise Exception('Invalid \'test_root\': {0}'.format(args.test_root))

# vim: set ts=2 sw=2 expandtab:
