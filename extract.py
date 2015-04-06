#pylint: disable-alnt: disable-all
import os
import argparse
import zipfile
import tempfile
import shutil
import fnmatch


# The conventional name of the folder within the CMS' submission.zip
SUBMISSION_DIR_NAME = 'Submissions'

def clean_empty_directories(root):
  '''Recursively delete empty directories starting at the 'root'.'''
  if os.path.isfile(root):
    return
  for item in os.listdir(root):
    path = os.path.join(root, item)
    if os.path.isdir(path):
      clean_empty_directories(path)
  if len(os.listdir(root)) == 0:
    os.rmdir(root)


def extract_zip(filepath, destination=None):
  '''Extract the specified zip file in either the 'destination' directory, if
  specified, or in the parent directory of the zip file. Delete the zip file
  after the contents have been extracted.'''
  with zipfile.ZipFile(filepath) as source_zip:
    parent_folder = os.path.dirname(os.path.abspath(filepath))
    destination = parent_folder if destination == None else destination
    source_zip.extractall(destination)
    os.remove(filepath)


def walk_and_extract_archives(root):
  '''Walk through the tree at 'root' once, extracting all the zip files
  so encountered in their parents' directory.'''
  archive_count = 0
  for root, _, files in os.walk(root):
    for f in files:
      path = os.path.join(root, f)
      if path.endswith('.zip'):
        extract_zip(path)
        archive_count += 1
  return archive_count


def extract(root, destination=None):
  '''Extract the zip file at 'root' into the directory 'destination', or to 
  the zip file's parent if 'destination' is None.'''
  if root.endswith('.zip'):
    if destination == None:
      destination = os.path.basename(root)[:-4]
    extract_zip(root, destination)
  while walk_and_extract_archives(destination) > 0:
    pass


def collapse_and_filter_directory(root, fnmatch_pattern):
  '''Collect all files that match 'fnmatch_pattern' into root, and delete
  everything else.'''
  temp_dir = tempfile.mkdtemp()
  for local_root, _, files in os.walk(root):
    for f in files:
      if fnmatch.fnmatch(f, fnmatch_pattern):
        path = os.path.join(local_root, f)
        shutil.copyfile(path, os.path.join(temp_dir, f))
  shutil.rmtree(root)
  shutil.copytree(temp_dir, root)
  shutil.rmtree(temp_dir)


def move(leftpath, rightpath, overwrite=False):
  '''Move the item 'leftpath' to the item 'rightpath'. Returns True if the
  item was actually overwritten or moved.'''
  if os.path.exists(rightpath):
    if overwrite:
      if os.path.isdir(rightpath):
        shutil.rmtree(rightpath)
        shutil.copytree(leftpath, rightpath)
      else:
        os.remove(rightpath)
        os.rename(leftpath, rightpath)
    return True
  else:
    shutil.move(leftpath, rightpath)
    return True
  return False


def process_submission(submission, destination, clean_empty, overwrite=False,
    file_pattern='*.py'):
  '''Extract and cleanup a standard submission.'''
  extract_dir = tempfile.mkdtemp()
  extracted_root = os.path.join(extract_dir, SUBMISSION_DIR_NAME)
  existing_root = os.path.join(destination)
  extract(submission, extract_dir)
  if not os.path.exists(existing_root):
    os.makedirs(existing_root)
  for f in os.listdir(extracted_root):
      extracted_directory = os.path.join(extracted_root, f)
      existing_directory = os.path.join(existing_root, f)
      if move(extracted_directory, existing_directory, overwrite):
        collapse_and_filter_directory(existing_directory, file_pattern)  
  shutil.rmtree(extract_dir)
  if clean_empty:
    clean_empty_directories(destination)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Robustly extracts the ' + 
      'submission zip files downloaded from Cornell\'s CMS system.',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument('-s', '--submission', help='The zip file that ' +
      'contains all the students\' submitted file.', default='submissions.zip')

  parser.add_argument('-d', '--destination', help='The directory to which ' +
      'the student\'s code will be extracted to.', default='code')

  parser.add_argument('-e', '--clean-empty-directories', help='If this option '+
      'is set, this script will attempt to remove all the empty directories ' +
      'from the extracted tree.', action='store_true', default=False)

  args = parser.parse_args()
  process_submission(args.submission, args.destination,
      args.clean_empty_directories)

# vim: set ts=2 sw=2 expandtab:
