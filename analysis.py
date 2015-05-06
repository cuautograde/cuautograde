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
import re
from matplotlib.font_manager import FontProperties
import matplotlib.ticker as ticker  

OUTCOME_TYPES = ['successes', 'errors', 'failures', 'aborted', 'skipped',
    'expectedFailures', 'unexpectedSuccesses']

OUTCOME_COLORS = {'errors': 'm', 'failures': 'r', 'skipped': 'c',
    'successes': 'g', 'aborted': 'y', 'expectedFailures': 'b',
    'unexpectedSuccesses': 'k'}

class GroupStatistics(object):
  '''Represents the computed statistics for a single group of one or more
  students being tested.'''

  def __init__(self, group_members, results_dict):
    '''group_members is an list of the members of a group od students.
    results_dict is a dictionary mapping the various outcome types to their
    values'''
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
    '''Formats the names of the group members.'''
    '''Given a list of one or more NetIDs, return a formatted'''
    if len(self.members) == 1:
      return 'Single person group {0}'.format(self.members[0])
    else:
      return 'Group of ' + ', '.join(self.members[:-1]) + ' and ' + \
        str(self.members[-1])

  def get_dir_name(self):
    '''Returns the name of the group folder as CMS would produce.'''
    assert len(self.members) <= 2
    if len(self.members) == 1:
      return self.members[0]
    else:
      return 'group_of_{}_{}'.format(self.members[0], self.members[1])

  def get_grade(self, weights, offset):
    '''Return the numerical grade of the group. The weights parameter, if
    specified, must either be a single number or a dictionary of tests mapping
    the specific weights for those tests.'''
    assert isinstance(weights, numbers.Number) or \
        (isinstance(weights, dict) and len(weights) == len(self.allTests))
    singular_weight = 1
    if isinstance(weights, numbers.Number):
      singular_weight = weights
      weights = dict()
    grade = offset
    for test in itertools.chain(self.successes, self.expectedFailures):
      grade += weights.get(test, singular_weight)
    return grade

  def test_count(self):
    '''Return the number of tests performed on the group.'''
    return len(self.allTests)

  def unsuccessful_count(self):
    return len(self.errors) + len(self.failures) + len(self.skipped) + \
        len(self.unexpectedSuccesses) + len(self.aborted)
    
  def success_count(self):
    return self.test_count() - self.unsuccessful_count()

  def pretty_print_category(self, name):
    '''Formats a single the tests results for a single outcome type.'''
    item = getattr(self, name)
    if item is None or len(item) == 0:
      return ''
    output = '{} ({}/{})\n\n'.format(name.upper(), len(item), self.test_count())
    if isinstance(item, dict):
      for k, v in item.iteritems():
        mod_name, class_name, func_name = k.split('.')
        output += '{0}.{1}:\n'.format(class_name, func_name)
        if self.allTests[k] is not None and len(self.allTests[k]) > 0:
          output += '\n'.join(textwrap.wrap(self.allTests[k], 80)) + '\n'
        output += v + '\n\n'
    else:
      for i in item:
        mod_name, class_name, func_name = i.split('.')
        output += '{0}.{1}\n'.format(class_name, func_name)
        if self.allTests[i] is not None and len(self.allTests[i]) > 0:
          output += '\n'.join(textwrap.wrap(self.allTests[i], 80)) + '\n'
    output += ('-' * 80) + '\n'
    return output

  def __str__(self, *args):
    '''Return a formatted string containing a prettified name of the group
    along with a summary of the test outcomes.'''
    output = self.format_group() + '\n\n'
    output += self.pretty_print_category('successes')
    output += self.pretty_print_category('errors')
    output += self.pretty_print_category('failures')
    output += self.pretty_print_category('aborted')
    output += self.pretty_print_category('skipped')
    output += self.pretty_print_category('unexpectedSuccesses')
    return output
  
  @classmethod
  def from_file(cls, filename):
    '''Create a GroupStatistics instance by reading in a json dictionary
    storing the results dictionary. The directory containing the file is
    assumed to contain the NetIDs of the members of the group.'''
    base = os.path.split(os.path.split(os.path.abspath(filename))[0])[1]
    assert os.path.isfile(filename), filename
    with open(filename) as result_file:
      return cls(re.findall('([a-z]+[0-9]+)', base), json.load(result_file))


class StatisticsSet(object):
  '''A collection of statistics for multiple groups.'''

  def __init__(self, instances):
    self.instances = list(instances)

  @classmethod
  def from_directory(cls, root_dir, result_file_path):
    '''Return a list of GroupStatistics for all the groups in a given 
    directory.'''
    assert os.path.isdir(root_dir)
    stat_list = []
    for f in os.listdir(root_dir):
      path = os.path.join(root_dir, f, result_file_path)
      if os.path.isfile(path):
        stat_list.append(GroupStatistics.from_file(path))
    return cls(stat_list)

  def get_test_performance(self, test_identifier):
    '''Return a dictionary mapping the outcome types to the instances of each
    type of outcome for the given test_identifier.'''
    stat_map = {k : [] for k in OUTCOME_TYPES}
    for t in OUTCOME_TYPES:
      for i in self.instances:
        if test_identifier in getattr(i, t):
          stat_map[t].append(i)
    return stat_map

  def format_test_performance(self, test_identifier):
    '''Format the outcomes of a particular test in terms of outcomes for the
    groups in this set.'''
    output = test_identifier + '\n\n'
    for c, f in self.get_test_performance(test_identifier).iteritems():
      if len(f) > 0:
        output += c.upper() + '\n' 
      for g in f:
        output += g.format_group() + '\n'
      if len(f) > 0:
        output += '\n'
    return output + ('-' * 80) + '\n'

  def write_test_breakdown(self, filename):
    '''Write the test-wise breakdown of the test suite to the specified file.'''
    assert len(self.instances) > 0
    with open(filename, 'w') as breakdown_file:
      for t in self.instances[0].allTests:
        breakdown_file.write(self.format_test_performance(t))

  def write_formatted_results(self, root_dir, result_file_path):
    '''Write the results of the test run to a human readable text file,
    relative to the root directory.'''
    for i in self.instances:
      path = os.path.join(root_dir, i.get_dir_name(), result_file_path) 
      assert os.path.isfile(path)
      with open(path) as f:
        f.write(i.__str__)

  def get_histogram(self):
    '''Get a histogram of test outcomes by type.'''
    assert len(self.instances) > 0
    template = {outcome: 0 for outcome in OUTCOME_TYPES}
    # Dictionary that maps each test to another dictionary that keeps a out
    # of the observed number of each of the possible outcomes for that test
    dist = {k: dict(template) for k in self.instances[0].allTests.keys()}

    for i in self.instances:
      for cat_name in OUTCOME_TYPES:
        for t in dist.keys():
          if t in getattr(i, cat_name):
            if not cat_name in dist[t]:
              dist[t][cat_name] = 0
            dist[t][cat_name] += 1
    return dist

  def plot_error_type_vs_students(self, filename):
    assert len(self.instances) > 0
    bins = self.get_histogram()
    fig = plt.figure()
    p = fig.add_subplot(111)
    tests = sorted(bins.keys())
    bottoms = [0] * len(tests)
    barPlots = []
    for outcome in OUTCOME_TYPES:
      results = [bins[t][outcome] for t in tests]
      if not any(results):
        continue
      a = p.bar(range(len(bins)), results, bottom=bottoms,
          color=OUTCOME_COLORS[outcome])
      bottoms = [bottoms[i] + results[i] for i in range(len(tests))]
      barPlots.append(a)
    fontP = FontProperties()
    fontP.set_size('x-small')
    p.legend(barPlots, OUTCOME_TYPES, prop=fontP, loc='lower right')
    ax = p.get_axes()
    ax.xaxis.set_major_formatter(ticker.NullFormatter())
    ax.xaxis.set_minor_locator(ticker.FixedLocator(
      [0.3 + i for i in range(len(tests))]))
    labels = [x[x.rfind('.')+1:] for x in tests]
    ax.xaxis.set_minor_formatter(ticker.FixedFormatter(labels))
    for t in ax.get_xminorticklabels():
      t.set_rotation(90)
    p.set_ylim(0, len(self.instances))
    p.set_title('Distribution of the various errors made by the students ' +
        '(count: {0})'.format(len(self.instances)))
    p.set_ylabel('Number of Groups')
    fig.tight_layout()
    fig.savefig(filename)

  def plot_error_count_vs_students(self, filename):
    assert len(self.instances) > 0
    bins = {i: 0 for i in range(len(self.instances[0].allTests) + 1)}
    for i in self.instances:
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

  def fill_csv(self, mapping, csv_file, output_file, weights_map, offset,
      additionalSources, verbose=False):
    p = GradeFileProcessor(csv_file, output_file)
    for g in self.instances:
      subs_values = dict()
      for func_name, rec_name in mapping.iteritems():
        if weights_map == None or not func_name in weights_map:
          subs_values[rec_name] = getattr(g, func_name)(1, 0)
        else:
          subs_values[rec_name] = getattr(g, func_name)(weights_map[func_name],
            offset)
      p.update_records(g.members, subs_values,
          [GradeFileProcessor(x) for x in additionalSources])
    p.dump(output_file)


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
  
  def update_records(self, record_ids, subs_values, additionalSources=[]):
    if not hasattr(record_ids, '__iter__'):
      record_ids = [record_ids]
    for rec_id in record_ids:
      row_index = self.contents_index_map[rec_id]
      for k, v in subs_values.iteritems():
        if isinstance(v, numbers.Number):
          maxVal = []
          trueVal = v
          for s in additionalSources:
            curr = self.contents_list[row_index][self.headers_index_map[k]]
            if isinstance(curr, str):
              if len(curr) == 0:
                curr = 0
              else:
                curr = float(curr)
            if maxVal < curr:
              maxVal = curr
          if v < maxVal:
            v = curr 
          if trueVal != v:
            print 'WARN: The score for {0} was {1} but has decreased to {2}'.\
                format(rec_id, curr, v)
        self.contents_list[row_index][self.headers_index_map[k]] = v
  
  def dump(self, filename):
    with open(filename, 'wb') as out_file:
      w = csv.writer(out_file)
      w.writerow(self.headers_list)
      w.writerows(self.contents_list)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Summarize the test results',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  
  parser.add_argument('test_results_directory', help='The directory ' +
      'containing all the students test results.')

  parser.add_argument('-f', '--result-filename', help='The name of the ' +
      'result file in the student\'s result directory', default='results.json')

  parser.add_argument('-c', '--csv-result-file', help='Zero or more template ' +
      'files downloaded from CMS for adding grades. The max of the grades ' +
      'will be written to the output CSV file specified.', nargs='*')

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

  parser.add_argument('-p', '--human-readable-summary', help='The file to ' +
      'store a human-readable summary of tests results by in the students\' ' +
      'results folder.', default=None)
  
  parser.add_argument('-w', '--weight-per-test', help='The weight assigned ' +
      'to each test to compute the grade.', default=1, type=float)

  parser.add_argument('-q', '--offset-points', help='Points added to a total ' +
      'grade. Must be positive right now.', default=0, type=float)
  
  parser.add_argument('-v', '--verbose', help='Points added to a total ' +
      'grade. Must be positive right now.', default=False, action='store_true')
  
  parser.add_argument('-m', '--no-max', help='Disable the feature that ' +
      'grades to only increase and never decrease.', default=False,
      action='store_true')
  
  if len(sys.argv) == 1:
    parser.print_help()
    exit(-2)
 
  args = parser.parse_args()

  stat = StatisticsSet.from_directory(args.test_results_directory,
      args.result_filename)
  
  if args.csv_result_file is not None:
    if args.csv_result_output_file is None:
      args.csv_result_output_file = args.csv_result_file[0]
    stat.fill_csv({'get_grade': 'Code', '__str__': 'Add Comments'},
        args.csv_result_file[0], args.csv_result_output_file,
        {'get_grade' : args.weight_per_test}, args.offset_points,
        args.csv_result_file, args.verbose)
  
  if args.human_readable_summary is not None:
    stat.write_formatted_results(args.test_results_directory,
        args.human_readable_summary)
  
  if args.num_students_vs_num_errors_plot is not None:
    stat.plot_error_count_vs_students(args.num_students_vs_num_errors_plot)
  
  if args.num_students_by_error_type_plot:
    stat.plot_error_type_vs_students(args.num_students_by_error_type_plot)

  if args.breakdown_by_test is not None:
    stat.write_test_breakdown(args.breakdown_by_test)

# vim: set ts=2 sw=2 expandtab:
