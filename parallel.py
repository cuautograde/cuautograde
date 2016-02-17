from __future__ import print_function
import time
import argparse
import multiprocessing
import os
import threading
import subprocess
import unittest
import traceback
import sys

import process_isolation

def iter_not_string(i):
  return hasattr(i, '__iter__')

def run_jailed_module(root, module):
  context = process_isolation.default_context()
  context.ensure_started()
  try:
    context.client.call(os.chroot, root)
  except OSError:
    print('This script must br run with superuser priviledges.')

  runner = context.load_module('runner')
  runner.process_one_submission(module, '/', overwrite_existing_results=True)


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
        r = subprocess.call(param)
        with results_lock:
          results.append((id, r))
          time_elapsed = time.time() - start_time
          avg_time = time_elapsed / len(results)
          tasks_done = len(results)
          projected_time = avg_time * (total_task_count - tasks_done) / 60
          # pylint: disable=E1601
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


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='This script is used to run ' +
    'several tests at once. The tests must be designed to follow the ' +
    'pattern described in the README.md',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument('module', help='The module containing tests to be run.')

  parser.add_argument('batch_test_root', help='The directory containing ' +
    'subdirectories, each of which contain an instance of the modules to be ' +
    'tested.')

  parser.add_argument('-r', '--result-file-path', help='The path to the file, '+
    'relative to the directory containing the test modules, to store the ' +
    'results as JSON objects.', default='results.json')

  parser.add_argument('-t', '--timeout', help='The max number of seconds a ' +
    'test is allowed to run.', default=600, type=float)

  parser.add_argument('-o', '--overwrite-existing-results', help='Indicates ' +
    'what action to take when a result file already exists',
    action='store_true', default=False)

  parser.add_argument('-v', '--verbose', help='Show the result of every test.',
    action='store_true', default=False)

  if len(sys.argv) == 1:
    parser.print_help()
    exit(-2)

  args = parser.parse_args()

  test_roots = []
  result_files = []
  for group in os.listdir(args.batch_test_root):
    instance_root = os.path.join(args.batch_test_root, group)
    if os.path.isdir(instance_root):
      test_roots.append(instance_root)

  process_count = multiprocessing.cpu_count()



  params = ['python', 'runner.py', args.module, test_roots,
      '-t', str(args.timeout), '-r', args.result_file_path]

  if args.overwrite_existing_results:
    params.append('-o')

  if args.verbose:
    params.append('-v')

  res = distribute_system_command(process_count, args.timeout, *params)

  non_zero_indicies = [i for i, e in enumerate(res) if e != 0]
  # pylint: disable=E1601
  print '\n' + ('-' * 80) + '\n'
  for i in non_zero_indicies:
    base = os.path.basename(test_roots[i])
    # pylint: disable=E1601
    print '{0} returned non-zero return code ({1})'.format(base, res[i])

# vim: set ts=2 sw=2 expandtab:
