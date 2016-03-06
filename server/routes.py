from __future__ import print_function
from flask import Flask, render_template, request
from werkzeug import secure_filename
import argparse
import json
import os
import random
import string
import shutil
import sys

sys.path.append('..')
import extract

app = Flask(__name__, static_url_path='/static')

def byteify(input):
    '''Borrowed from: http://stackoverflow.com/a/13105359.'''
    if isinstance(input, dict):
        return {byteify(key): byteify(value)
                for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input

def json_load(filename):
    with open(filename, 'r') as infile:
        return byteify(json.load(infile))


# Initialize the default parameters
config = json_load('default_config.json')

def check_if_name_exists(name):
    '''Returns True is the specified name exists in the upload directory.'''
    upload_dir = os.path.expanduser(config['upload_dir'])
    return os.path.exists(upload_dir) and name in os.listdir(upload_dir)


def check_if_results_ready(name):
    '''Returns True if the daemon has completed processing this submisstion.'''
    if not check_if_name_exists(name):
        return False
    else:
        upload_dir = os.path.expanduser(config['upload_dir'])
        return config['sentinel'] in os.listdir(os.path.join(upload_dir, name))


def generate_dirname():
    '''Generates a filename for the student submission.'''
    name = None
    while name is None or check_if_name_exists(name):
        size = config['filename_length']
        chars = string.ascii_lowercase + string.digits
        name = ''.join(random.choice(chars) for _ in range(size))
    return name


@app.route('/')
def default_route():
    return render_template('index.html', config=config)


@app.route('/submit', methods=['POST'])
def accept_submission():
    infile = request.files['submission']
    if infile:
        upload_dir_root = os.path.expanduser(config['upload_dir'])
        assert upload_dir_root != None, 'upload_dir must be specified in config'
        if not os.path.isdir(upload_dir_root):
            os.makedirs(upload_dir_root)
        name = generate_dirname()
        upload_dir = os.path.join(upload_dir_root, name)
        os.mkdir(upload_dir)
        zipfile = os.path.join(upload_dir, name + '.zip')
        try:
            infile.save(zipfile)

            extract.extract(zipfile, upload_dir)
            extract.collapse_and_filter_directory(upload_dir, ['*.py'])
        except:
            raise
            try:
                shutil.rmtree(upload_dir)
                pass
            except:
                pass
            return 'Error occurred while processing your zip file.'

        return 'Your ID is {}. Save it to access your results.'.format(name)
    return 'Invalid submission.'


@app.route('/results')
def display_results():
    id = request.args.get('id')
    if not id:
        return 'No ID specified.'
    if check_if_results_ready(id):
        res = os.path.expanduser(os.path.join(config['upload_dir'], id,
           'results.json'))
        if not os.path.isfile(res):
            return 'Your submission was malformed, so no unit tests could run.'
        results = json_load(res)
        return  'Successes: {}, '.format(len(results['successes'])) + \
                'Failures:  {}, '.format(len(results['failures']))  + \
                'Errors:    {}, '.format(len(results['errors']))    + \
                'Aborted:   {}, '.format(len(results['aborted']))   + \
                'Total:     {}'.format(len(results['allTests']))
    else:
        return 'Result not available.'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Autograder web service.',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-c', '--config', help='The config file. See the' +
            'template for an example.', default=None)

    args = parser.parse_args()

    # Update configs if specified by the user
    if args.config is not None:
        if os.path.isfile(args.config):
            try:
                # Read the new config file and override the defaults
                overriding_config = json_load(args.config)
                for k, v in overriding_config.items():
                    config[k] = v
            except:
                print('Error reading the config file {}.'.format(args.config))
                sys.exit(-1)
        else:
            print('{} is not a path to a valid file.'.format(args.config))
    app.run(host='0.0.0.0', debug=True)
