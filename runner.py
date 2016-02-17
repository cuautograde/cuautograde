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


def redirect_console(where=None):
  '''Send all prints and error prints to the specified stream or to
  the platform's equivalent of the Unix /dev/null.'''
  if where is None:
    f = open(os.devnull, 'w')
  else:
    f = open(where, 'w')
  sys.stdout = f
  sys.stderr = f


def displayln(s):
  '''Write the specified string to the original console output stream.'''
  with console_lock:
    console.write('{0}\n'.format(s))


def iter_not_string(i):
  '''Return True if the specified object is iterable but is not a string.'''
  return hasattr(i, '__iter__')


def doc_for(test):
  '''Return the docstring for a given test identifier.'''
  mod_name, class_name, func_name = test.id().split('.')
  return getattr(test, func_name).__doc__


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
  and respond to requests for stoping, such as due to timeouts.

  Note that this class intentionally uses the Python threading module
  instead of the multiprocessing module. The typical use-case of this
  class is to provide a way to execute tasks in a relatively
  starvation-proof manner, that is, to allow all rest of the tasks to
  make progress even if a few of the tasks are not making progress. It
  specifically does not provide any guarentees as to whether the tasks will
  actually be executed in parallel (which, in case if CPython, is well-known to
  not be true).'''

  def __init__(self, tasks, args, finalizers=None):
    ''''tasks' is a list of single parameter functions corresponding to a
    single interruptible task to be performed by this thread group.
    'args' is a list (same size as 'tasks') of arguments corresponding to
    those expected by the respective task. 'finalizers' are single parameter
    functions called after the task, and receives the same parameter as the
    corresponding task.'''

    # The thread group is itself managed by a thread
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

    assert len(tasks) == len(args), 'Length of \'tasks\' must be the same ' +\
      'as length of \'args\''

    assert len(tasks) == len(finalizers), 'Length of \'tasks\' must be the ' +\
      'same as length of \'finalizers\''

    for task, arg, finalizer in zip (tasks, args, finalizers):
      # Define what each thread in the thread group is supposed to do
      def unit_work(param):
        task(param) # First perform the task
        if finalizer is not None: # Then if finalizer is not None, execute it
          finalizer(param)
        with self.running_status_lock: # Finally update the active thread count
          self.tasks_running_count -= 1
          if self.tasks_running_count == 0: # If the count goes to zero, signal
            self.is_running = False
            self.running_status_changed.notify_all()

      thread = threading.Thread(target=unit_work, args=(arg,))
      # The individual tasks are daemon, so they terminate as soon the the
      # group controller terminates
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
    '''Set a timeout monitor that waits for the specified number of seconds
    before signalling the thread group controller to terminate.'''
    # Define the task of the timeout monitor
    def task():
      start_time = time.time()
      while time.time() - start_time < timeout_in_seconds:
        time.sleep(timeout_in_seconds - (time.time() - start_time))
      self.stop_all_tasks()
    thread = threading.Thread(target=task)
    thread.daemon = True # Daemon so that it dies when the tasks threads die
    thread.start()

  @classmethod
  def run_tasks_until_timeout(cls, tasks, args, finalizers, timeout):
    '''This function takes in a list of tasks and runs them up to timeout
    seconds.'''
    tg = cls(tasks, args, finalizers)
    tg.start()
    tg.set_timeout(timeout)
    tg.join()


class SynchronizedTestResult(unittest.TestResult):
  '''A simple test result aggregator that build on top of unittest.TestResult
  to account for concurrent updates.'''

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
      'allTests': {t.id(): doc_for(t) for t in all_tests}
    }
    processed_union = set().union(s['errors'].keys(), s['failures'].keys(),
        s['successes'], s['skipped'].keys(), s['expectedFailures'].keys(),
        s['unexpectedSuccesses'])
    s['aborted'] = list(set(x.id() for x in all_tests) - processed_union)
    return s


class TimeoutTestRunner(object):
  '''A unit test runner with support for timeouts built on top of the
  InterruptibleThreadGroup.'''

  def __init__(self, timeout):
    self.timeout = timeout

  @staticmethod
  def process_test_cases(entity, func_name, already_processed=set()):
    '''Runs the specified class function of the TestCase object encountered,
    recusively starting at root, ensuring that each class is processed exactly
    once.'''
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
    '''Executes the given test suite and returns the collected results.'''
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
    return resulti


def process_one_submission(module, test_root, result_file_path='results.json',
    timeout=600.0, overwrite_existing_results=False, verbose=False,
    redir_console=None):

  # Redirect console only once the arguments have been parsed
  redirect_console(redir_console)

  # Check if the module name was accidentally specified with .py extension
  # and if so, correct it
  if module.endswith('.py'):
    module = module[:-3]

  # First check if the result file exists
  result_file_path = os.path.join(test_root, result_file_path)
  basename = os.path.basename(os.path.abspath(test_root))
  if os.path.isfile(result_file_path) and not overwrite_existing_results:
    displayln('Results already exist for {0}'.format(basename))
    sys.stdout.close()
    exit(1)

  # Typically, this module will be run in the same directory so we need to
  # make the symlinks in those directory accessible by adding the current
  # working directory to the path
  sys.path.append(os.getcwd())

  # Check if the specified test root is valid
  if not os.path.isdir(test_root):
    sys.stdout.close()
    raise Exception('Invalid \'test_root\': {0}'.format(args.test_root))

  # Append the test root to the python path so that the test module can be
  # imported directly
  sys.path.append(test_root)

  # Import the test module and run the tests contained in it
  m = __import__(module)
  tests = unittest.defaultTestLoader.loadTestsFromModule(m)
  result = TimeoutTestRunner(timeout).run(tests, verbose)
  summary = result.summarize(tests)

  # Write the test results as a JSON file
  with open(result_file_path, 'w') as result_file:
    json.dump(summary, result_file, indent=True)

  # Display a summary of the students' results to let the test runner know
  # the test runner is making progress
  displayln(('{0}: Successful={1}/{6}, Errors={2}/{6}, Failed={3}/{6}, ' +
    'Aborted={4}/{6}, Skipped={5}/{6}').format(basename,
    len(summary['successes']), len(summary['errors']),
    len(summary['failures']), len(summary['aborted']),
    len(summary['skipped']), len(summary['allTests'])))

  if len(summary['aborted']) > 0:
    sys.stdout.close()
    exit(2)
  sys.stdout.close()


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='This module is used to run ' +
    'tests on a single instance. The tests must be contained in a single ' +
    'module, and must use the Python\'s unittest framework. This module  ' +
    'runs the tests in separate threads (not processes) and optionally ' +
    'enforces timeouts on the tests. The results it generates are stored ' +
    'in a JSON file relative to the student\'s code directory.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument('module', help='The module containing tests to be run.')

  parser.add_argument('test_root', help='The directory containing the modules '+
    'to be tested.')

  parser.add_argument('-r', '--result-file-path', help='The path to the file, '+
    'relative to test_root, to store the results as JSON objects.',
    default='results.json')

  parser.add_argument('-t', '--timeout', help='The max number of seconds a ' +
    'test is allowed to run.', default=600, type=float)

  parser.add_argument('-o', '--overwrite-existing-results', help='Indicates ' +
    'what action to take when a result file already exists',
    action='store_true', default=False)

  parser.add_argument('-v', '--verbose', help='Show the result of every test.',
    action='store_true', default=False)

  parser.add_argument('-c', '--redir-console', help='Redirect console to this '+
    'instead of null device.', default=None)

  # if the user runs the module without any arguments then display the help menu
  if len(sys.argv) == 1:
    parser.print_help()
    sys.stdout.close()
    exit(-2)

  args = parser.parse_args()

  process_one_submission(args.module, args.test_root, args.result_file_path,
    args.timeout, args.overwrite_exisiting_results, args.verbose,
    args.redir_console)

# vim: set ts=2 sw=2 expandtab:
