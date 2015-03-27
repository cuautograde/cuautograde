import json
import os
import argparse


def pretty_print_test_results(group, filename):
  if not os.path.isfile(filename):
    return
  with open(filename) as result_file:
    res = json.load(result_file)
    print
    if len(group) == 2:
      print 'Group of {0} and {1}'.format(group[0], group[1]),
    else:
      print 'Single person group {0}'.format(group[0]),
    successes = len(res['testids']) - len(res['failures']) - len(res['errors'])
    print 'Failed: {0}, Errors: {1}, Successes {2}'.format(len(res['failures']),
        len(res['errors']), successes)
    print
   
  if len(res['failures']) > 0:
    print '--------'
    print 'Failures:'
    print '--------'
    print
    for k, v in res['failures'].iteritems():
      print k[9:]
      info = v.rsplit('\n')
      print info[-2]
      print
    
  if len(res['errors']) > 0:
    print '------'
    print 'Errors:'
    print '------'
    print
    for k, v in res['errors'].iteritems():
      print k[9:]
      print v
  
  print '-' * 80


def split_group_dir_name(groupdirname):
    '''
        groupdirname -- the directory name corresponding to the group used by
        CMS
        A list containing the netIDs of group members
    '''

    group_prefix = 'group_of_'
    # If the group consists of only one person
    if not groupdirname.startswith(group_prefix):
        return [groupdirname]

    # Delete group prefix
    netids = groupdirname.replace(group_prefix, '')
    return netids.split('_')


def gather_test_results(solution_dir, result_file):
  params = []
  for g in sorted(os.listdir(solution_dir)):
    if os.path.isdir(os.path.join(solution_dir, g)):
      group = split_group_dir_name(g)
      params.append((group, os.path.join(solution_dir, g, result_file)))
  return params


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Summarize the test results',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  
  parser.add_argument('-r', '--test-results-directory', help='The directory ' +
      'containing all the students test results.', default='code')

  parser.add_argument('-f', '--result-file-name', help='The name of the ' +
      'result file in the student\'s result directory', default='results.json')
 
  args = parser.parse_args()

  p = gather_test_results(args.test_results_directory, args.result_file_name)

  for group in p:
    pretty_print_test_results(*group)

# vim: set ts=2 sw=2 expandtab:
