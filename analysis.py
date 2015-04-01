import json
import os
import argparse
import matplotlib.pyplot as plt


class GroupStatistics(object):
  def __init__(self, group_members, results_dict):
    self.members = group_members
    for stat, val in results_dict.iteritems():
      setattr(self, stat, val)

  def format_group(self):
    '''Given a list of one or more NetIDs, return a formatted'''
    if len(self.members) == 1:
      return 'Single person group {0}'.format(self.members[0])
    else:
      return 'Group of ' + ', '.join(self.members[:-1]) + ' and ' + \
        str(self.members[-1])

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
    base = os.path.basename(filename)
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

  @staticmethod
  def pretty_print_category(name):
    item = getattr(self, name)
    if len(item) == 0:
      return ''
    output = name + '\n\n'
    if isinstance(item, dict):
      for k, v in item.iteritems():
        mod_name, class_name, func_name = k.split('.')
        output += '{0}.{1}\n'.format(class_name, func_name)
        output += v.split('\n')[-2] + '\n\n'
    else:
      for i in item:
        mod_name, class_name, func_name = k.split('.')
        output += '{0}.{1}\n\n'.format(class_name, func_name)
    output += ('-' * 80) + '\n'

  def __str__(self):
    output = self.format_group() + '\n\n'
    output += GroupStatistics.pretty_print_category('errors')
    output += GroupStatistics.pretty_print_category('failures')
    output += GroupStatistics.pretty_print_category('aborted')
    output += GroupStatistics.pretty_print_category('skipped')
    output += GroupStatistics.pretty_print_category('unexpectedSuccesses')
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

  @classmethod
  def get_histogram(cls, instances):
    assert len(instances) > 0
    dist = {k: 0 for k in instances[0].allTests}
    for i in instances:
      GroupStatistics.update_count('errors', dist, i)
      GroupStatistics.update_count('failures', dist, i)
      GroupStatistics.update_count('aborted', dist, i)
      GroupStatistics.update_count('skipped', dist, i)
      GroupStatistics.update_count('unexpectedSuccesses', dist, i)
    return dist

  @classmethod
  def plot_error_count_vs_students(cls, instances):
    assert len(instances) > 0
    bins = cls.get_histogram(instances)
    fig = plt.figure()
    p = fig.add_subplot(111)
    p.bar(range(len(bins)), bins.values())
    labels = [x[x.rfind('.')+1:] for x in bins.keys()]
    p.set_xticks(range(len(bins)))
    p.set_xticklabels(labels, rotation=90)
    p.set_title('Distribution of the number of errors made by the students')
    p.set_ylabel('Number of Groups')
    fig.tight_layout()
    fig.savefig('errors_vs_num_students.png')

  @classmethod
  def plot_error_type_vs_students(cls, instances):
    assert len(instances) > 0
    bins = {i: 0 for i in range(len(instances[0].allTests) + 1)}
    for i in instances:
      bins[i.unsuccessful_count()] += 1
    fig = plt.figure()
    p = fig.add_subplot(111)
    p.bar(bins.keys(), bins.values())
    p.set_title('Distribution of the various errors made by the students')
    p.set_xlabel('Number of Errors')
    p.set_ylabel('Number of Groups')
    fig.savefig('num_errors_vs_num_students.png', bbox_inches='tight')


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Summarize the test results',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  
  parser.add_argument('-r', '--test-results-directory', help='The directory ' +
      'containing all the students test results.', default='code')

  parser.add_argument('-f', '--result-filename', help='The name of the ' +
      'result file in the student\'s result directory', default='results.json')
 
  args = parser.parse_args()

  instances = GroupStatistics.from_directory(args.test_results_directory,
      args.result_filename)
  GroupStatistics.plot_error_count_vs_students(instances)
  GroupStatistics.plot_error_type_vs_students(instances)

# vim: set ts=2 sw=2 expandtab:
