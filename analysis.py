import json
import os
import argparse
import matplotlib.pyplot as plt
import numbers
import itertools
import csv
import sys
import textwrap
import math

OUTCOME_TYPES = ['errors', 'failures', 'skipped', 'successes', 'aborted',
    'expectedFailures', 'unexpectedSuccesses']

class GroupStatistics(object):
  def __init__(self, group_members, results_dict):
    self.members = group_members
    self.errors = results_dict['errors']
    self.failures = results_dict['failures']
    self.skipped = results_dict['skipped']
    self.successes = results_dict['successes']
    self.unexpectedSuccesses = results_dict['unexpectedSuccesses']
    self.aborted = results_dict['aborted']
    self.expectedFailures = results_dict['expectedFailures']
    self.allTests = results_dict['allTests']

  def format_group(self):
    '''Given a list of one or more NetIDs, return a formatted'''
    if len(self.members) == 1:
      return 'Single person group {0}'.format(self.members[0])
    else:
      return 'Group of ' + ', '.join(self.members[:-1]) + ' and ' + \
        str(self.members[-1])

  def get_grade(self, weights=1):
    assert isinstance(weights, numbers.Number) or \
        (isinstance(weights, dict) and len(weights) == len(self.allTests))
    singular_weight = 1
    if isinstance(weights, numbers.Number):
      singular_weight = weights
      weights = dict()
    grade = 0
    for test in itertools.chain(self.successes, self.expectedFailures):
      grade += weights.get(test, singular_weight)
    return int(math.ceil(grade))

  @staticmethod
  def get_members_from_dir_name(groupdirname):
    group_prefix = 'group_of_'
    # If the group consists of only one person
    if not groupdirname.startswith(group_prefix):
      return [groupdirname]
    # Delete group prefix
    netids = groupdirname.replace(group_prefix, '')
    return netids.split('_')

  @classmethod
  def from_file(cls, filename):
    base = os.path.split(os.path.split(os.path.abspath(filename))[0])[1]
    assert os.path.isfile(filename), filename
    with open(filename) as result_file:
      return cls(cls.get_members_from_dir_name(base), json.load(result_file))

  @classmethod
  def from_directory(cls, root_dir, result_file_path):
    assert os.path.isdir(root_dir)
    stat_list = []
    for f in os.listdir(root_dir):
      path = os.path.join(root_dir, f, result_file_path)
      if os.path.isfile(path):
        stat_list.append(cls.from_file(path))
    return stat_list

  def test_count(self):
    return len(self.allTests)

  def unsuccessful_count(self):
    return len(self.errors) + len(self.failures) + len(self.skipped) + \
        len(self.unexpectedSuccesses) + len(self.aborted)
    
  def success_count(self):
    return self.test_count() - self.unsuccessful_count()

  def pretty_print_category(self, name):
    item = getattr(self, name)
    if item is None or len(item) == 0:
      return ''
    output = name.upper() + '\n\n'
    if isinstance(item, dict):
      for k, v in item.iteritems():
        mod_name, class_name, func_name = k.split('.')
        output += '{0}.{1}:\n'.format(class_name, func_name)
        if self.allTests[k] is not None and len(self.allTests[k]) > 0:
          output += '\n'.join(textwrap.wrap(self.allTests[k], 80)) + '\n'
        output += v.split('\n')[-2] + '\n\n'
    else:
      for i in item:
        mod_name, class_name, func_name = i.split('.')
        output += '{0}.{1}\n'.format(class_name, func_name)
        if self.allTests[i] is not None and len(self.allTests[i]) > 0:
          output += '\n'.join(textwrap.wrap(self.allTests[i], 80)) + '\n'
    output += ('-' * 80) + '\n'
    return output

  def __str__(self):
    output = self.format_group() + '\n\n'
    output += self.pretty_print_category('errors')
    output += self.pretty_print_category('failures')
    output += self.pretty_print_category('aborted')
    output += self.pretty_print_category('skipped')
    output += self.pretty_print_category('unexpectedSuccesses')
    return output

  @staticmethod
  def update_count(cat_name, dist, instance):
    item = getattr(instance, cat_name)
    if isinstance(item, dict):
      for k, v in item.iteritems():
        dist[k] += 1
    else:
      for v in item:
        dist[v] += 1

  @staticmethod
  def get_test_performance(instances, test_identifier):
    stat_map = dict()
    for t in OUTCOME_TYPES:
      stat_map[t] = []
      for i in instances:
        if test_identifier in getattr(i, t):
          stat_map[t].append(i)
    return stat_map

  @staticmethod
  def format_test_performance(instances, test_identifier):
    output = test_identifier + '\n\n'
    for c, f in GroupStatistics.get_test_performance(instances,
        test_identifier).iteritems():
      if len(f) > 0:
        output += c.upper() + '\n' 
      for g in f:
        output += g.format_group() + '\n'
      if len(f) > 0:
        output += '\n'
    return output + ('-' * 80) + '\n'

  @staticmethod
  def write_test_breakdown(instances, filename):
    assert len(instances) > 0
    with open(filename, 'w') as breakdown_file:
      for t in instances[0].allTests:
        breakdown_file.write(GroupStatistics.format_test_performance(instances, 
          t))

  @classmethod
  def get_histogram(cls, instances):
    assert len(instances) > 0
    dist = {k: 0 for k in instances[0].allTests.keys()}
    for i in instances:
      GroupStatistics.update_count('errors', dist, i)
      GroupStatistics.update_count('failures', dist, i)
      GroupStatistics.update_count('aborted', dist, i)
      GroupStatistics.update_count('skipped', dist, i)
      GroupStatistics.update_count('unexpectedSuccesses', dist, i)
    return dist

  @classmethod
  def plot_error_type_vs_students(cls, instances, filename):
    assert len(instances) > 0
    bins = cls.get_histogram(instances)
    fig = plt.figure()
    p = fig.add_subplot(111)
    p.bar(range(len(bins)), bins.values())
    labels = [x[x.rfind('.')+1:] for x in bins.keys()]
    p.set_xticks(range(len(bins)))
    p.set_xticklabels(labels, rotation=90)
    p.set_ylim(0, len(instances))
    p.set_title('Distribution of the various errors made by the students ' +
        '(count: {0})'.format(len(instances)))
    p.set_ylabel('Number of Groups')
    fig.tight_layout()
    fig.savefig(filename)

  @classmethod
  def plot_error_count_vs_students(cls, instances, filename):
    assert len(instances) > 0
    bins = {i: 0 for i in range(len(instances[0].allTests) + 1)}
    for i in instances:
      bins[i.unsuccessful_count()] += 1
    fig = plt.figure()
    p = fig.add_subplot(111)
    p.bar(range(len(bins)), bins.values())
    labels = bins.keys()
    p.set_xticks(range(len(bins)))
    p.set_xticklabels(labels)
    p.set_title('Distribution of the number of errors made by the students')
    p.set_xlabel('Number of Errors')
    p.set_ylabel('Number of Groups')
    fig.savefig(filename)


class GradeFileProcessor(object):
  def __init__(self, filename, result_filename=None):
    self.filename = filename
    self.result_filename = filename if not result_filename else result_filename
    with open(self.filename, 'r') as input_file:
      contents = list(csv.reader(input_file))
      assert len(contents) > 0
      self.headers_list = contents[0]
      self.headers_index_map = {k:i for i, k in enumerate(self.headers_list)}
      self.contents_list = contents[1:]
      self.contents_index_map = \
          {e[0]: i for i, e in enumerate(self.contents_list)}

      # Make all the rows match the number of the headers
      for i in range(len(self.contents_list)):
        diff = len(self.headers_list) - len(self.contents_list[i])
        assert diff >= 0
        if diff > 0:
          self.contents_list[i] += [''] * diff
  
  def update_records(self, record_ids, subs_values):
    if not hasattr(record_ids, '__iter__'):
      record_ids = [record_ids]
    for rec_id in record_ids:
      row_index = self.contents_index_map[rec_id]
      for k, v in subs_values.iteritems():
        self.contents_list[row_index][self.headers_index_map[k]] = v
  
  def dump(self, filename):
    with open(filename, 'wb') as out_file:
      w = csv.writer(out_file)
      w.writerow(self.headers_list)
      w.writerows(self.contents_list)


def groups_to_csv(groups, mapping, csv_file, output_file, weights_map=None):
  p = GradeFileProcessor(csv_file, output_file)
  for g in groups:
    subs_values = dict()
    for func_name, rec_name in mapping.iteritems():
      if weights_map == None or not func_name in weights_map:
        subs_values[rec_name] = getattr(g, func_name)()
      else:
        subs_values[rec_name] = getattr(g, func_name)(weights_map[func_name])
    p.update_records(g.members, subs_values)
  p.dump(output_file)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Summarize the test results',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  
  parser.add_argument('test_results_directory', help='The directory ' +
      'containing all the students test results.')

  parser.add_argument('-f', '--result-filename', help='The name of the ' +
      'result file in the student\'s result directory', default='results.json')

  parser.add_argument('-c', '--csv-result-file', help='The file downloaded ' +
      'from CMS for adding grades.', default=None)

  parser.add_argument('-o', '--csv-result-output-file', help='The CSV file ' +
      'to write the output to. Same ad csv-result-file if not specified.',
      default=None)

  parser.add_argument('-s', '--num-students-vs-num-errors-plot',
      help='The file to store the plot of number of students ' +
      'versus the number of errors.', default=None)

  parser.add_argument('-e', '--num-students-by-error-type-plot',
      help='The file to store the plot of the number of students for each ' +
      'type of error', default=None)

  parser.add_argument('-b', '--breakdown-by-test', help='The file to store ' +
      'the breakdown of tests results by test name.', default=None)
  
  parser.add_argument('-w', '--weight-per-test', help='The weight assigned ' +
      'to each test to compute the grade.', default=1, type=float)

  if len(sys.argv) == 1:
    parser.print_help()
    exit(-2)
 
  args = parser.parse_args()

  instances = GroupStatistics.from_directory(args.test_results_directory,
      args.result_filename)
  
  if args.csv_result_file is not None:
    if args.csv_result_output_file is None:
      args.csv_result_output_file = args.csv_result_file
    groups_to_csv(instances, {'get_grade': 'Code', '__str__': 'Add Comments'},
        args.csv_result_file, args.csv_result_output_file,
        {'get_grade' : args.weight_per_test})
  
  if args.num_students_vs_num_errors_plot is not None:
    GroupStatistics.plot_error_count_vs_students(instances,
        args.num_students_vs_num_errors_plot)
  
  if args.num_students_by_error_type_plot:
    GroupStatistics.plot_error_type_vs_students(instances,
        args.num_students_by_error_type_plot)

  if args.breakdown_by_test is not None:
    GroupStatistics.write_test_breakdown(instances, args.breakdown_by_test)

# vim: set ts=2 sw=2 expandtab:
