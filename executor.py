import time
import argparse
import multiprocessing
import os
import threading
import subprocess

DEVNULL = open(os.devnull, 'wb')

def iter_not_string(i):
  return hasattr(i, '__len__') and not isinstance(i, basestring)

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


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='This script is used to run ' +
    'several tests at once. The tests must be designed to follow a ' +
    'patter described in the README.md', prefix_chars='@')

  parser.add_argument('executable', help='The test script to run.')

  parser.add_argument('student_solution_root', help='The directory ' +
    'containing all of the students\' code to run tests on.')

  parser.add_argument('@r', '@@result-file-name', help='The name of the ' +
    'file to store results in. The file will be placed in the ' +
    'students\' respective solution directory', action='store',
    default='results.json')
  
  parser.add_argument('@t', '@@timeout', help='The max number of seconds a ' +
      'process is allowed to run.', default=600, type=float)

  parser.add_argument('@a', '@@additional-arguments', help='Any arguments ' +
    'pass to the executable.', nargs='*')

  args = parser.parse_args()
   
  solution_dirs = []
  result_files = []

  for group in os.listdir(args.student_solution_root):
    if os.path.isdir(os.path.join(args.student_solution_root, group)):
      solution_dirs.append(os.path.join(args.student_solution_root, group))
      result_files.append(os.path.join(args.student_solution_root, group,
        args.result_file_name))

  print 'Found {0} jobs.'.format(len(solution_dirs))

  process_count = 2 * multiprocessing.cpu_count()

  if args.additional_arguments:
    res = distribute_system_command(process_count, float(args.timeout),'python',
        args.executable, solution_dirs, result_files,*args.additional_arguments)
  else:
    res = distribute_system_command(process_count, float(args.timeout),'python',
        args.executable, solution_dirs, result_files)

# vim: set ts=2 sw=2 expandtab:
