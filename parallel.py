from __future__ import print_function
import time
import collections
import argparse
import multiprocessing.pool
import os
import sys
import process_isolation
import runner
import cv2

print(sys.path)

def run_jailed_test(module, deps, timeout, overwrite_existing_results, root):
  context = process_isolation.default_context()
  context.ensure_started()
  try:
    context.client.call(os.chroot, root)
  except OSError:
    print('This script must be run with superuser priviledges.')
    exit(-1)
  for d in deps:
    context.load_module(d, path=sys.path)
  context.load_module(module, path=sys.path)
  runner = context.load_module('cuautograde.runner', path=sys.path)
  return runner.process_one_submission(module, '/', timeout=timeout,
      overwrite_existing_results=overwrite_existing_results)

def run_jailed_test_helper(args):
  run_jailed_test(*args)


def run_batch(batch_root, module, deps, timeout, overwrite_existing_results):
  roots = [os.path.join(batch_root, r) for r in os.listdir(batch_root)]
  args = []
  for r in roots:
    a = (module, deps, timeout, overwrite_existing_results, r)
    args.append(a)
    run_jailed_test_helper(a)

def _run_batch(batch_root, module, timeout, overwrite_existing_results):
  roots = [os.path.join(batch_root, r) for r in os.listdir(batch_root)]
  args = []
  for r in roots:
    args.append((module, timeout, overwrite_existing_results, r))
  p = multiprocessing.pool.ThreadPool(processes=(2 * multiprocessing.cpu_count()))
  results = p.map_async(run_jailed_test_helper, args)
  p.close()
  p.join()
  res_dict = collections.defaultdict(list)
  for r in results.get():
    try:
      res_code = r.get()
    except Exception as ex:
      print(ex)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='This script is used to run ' +
    'several tests at once. The tests must be designed to follow the ' +
    'pattern described in the README.md',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument('batch_test_root', help='The directory containing ' +
    'subdirectories, each of which contain an instance of the modules to be ' +
    'tested.')

  parser.add_argument('module', help='The module containing tests to be run.')

  parser.add_argument('-t', '--timeout', help='The max number of seconds a ' +
    'test is allowed to run.', default=600, type=float)

  parser.add_argument('-o', '--overwrite-existing-results', help='Indicates ' +
    'what action to take when a result file already exists',
    action='store_true', default=False)

  if len(sys.argv) == 1:
    parser.print_help()
    exit(-2)

  args = parser.parse_args()

  run_batch(args.module, args.batch_test_root, args.timeout,
      args.overwrite_existing_results)

# vim: set ts=2 sw=2 expandtab:
