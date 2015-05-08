import argparse
import sys
import os
import fnmatch

import extract

def rename_contents(root, filematcher):
  '''For every directory within the specified 'root' folder, change the name
  of the file contained in the directory to that of the parent directory.
  Assuments that the directory only contains one file of the specified type.'''
  
  for d in os.listdir(root):
    if not os.path.isdir(os.path.join(root, d)):
      continue
    for f in os.listdir(os.path.join(root, d)):
      src = os.path.join(root, d, f)
      if os.path.isfile(src) and fnmatch.fnmatch(f, filematcher):
        i = f.rfind('.')
        if i < 1: # either not found or a dot file
          continue
        extension = f[i+1:] 
        dst = os.path.join(root, d, d + '.' + extension)
        print 'Renaming {} to {}'.format(src, dst)
        os.rename(src, dst)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='A utility to process student ' +
    'submissions in the form of PDF documents.')

  rename_contents('files', '*pdf')
  extract.collapse_and_filter_directory('files', '*.pdf')

# vim: set ts=2 sw=2 expandtab:
