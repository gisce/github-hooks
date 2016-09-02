#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function
from subprocess import Popen, PIPE
from os.path import join
from json import loads
from tempfile import mkdtemp
from shutil import rmtree
import sys


class TempDir(object):
    def __init__(self):
        self.dir = mkdtemp()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        rmtree(self.dir)


def arguments():
    with open(sys.argv[1], 'r') as jsf:
        payload = loads(jsf.read())
    return payload

output = ''
out = ''
payload = arguments()
http_res = payload['http_url'].split('/')
# 'http:'/''/'url'/
http_url = http_res[0]
if http_url == 'http:':
    http_url += '//'
    http_url += http_res[1] if http_res[1] != '' else http_res[2]
url = payload['ssh_url'] or payload['http_url']
if not url:
    output = 'Failed to get URL (was it in payload?)'
    print (output)
    exit(-1)
repo_name = payload['repo_name']        # Source Repository Name
source_branch = payload['branch_name']  # Source branch
project_id = payload['project_id']      # Source Project ID
item_id = payload['item_id']            # item PR id
merge_id = payload['merge_request_id']  # action PR id

lektor_path = '/var/www/devel.info'
branch_path = '{0}/branch/{1}'.format(lektor_path, source_branch)
mr_path = '{}/PR/'.format(lektor_path)

with TempDir() as tmp:
    tmp_dir = tmp.dir
    output += ('Creat Directori temporal: {} |'.format(tmp_dir))
    command = ''
    if source_branch != 'None':
        output += "Clonant el repositori '{0}', amb la branca '{1}' ...".format(
            repo_name, source_branch
        )
        command = 'git clone {0} --branch {1}'.format(url, source_branch)
    else:
        output += "Clonant el repositori '{0}' ...".format(repo_name)
        command = 'git clone {}'.format(url)

    new_clone = Popen(
        command.split(), cwd=tmp_dir, stdout=PIPE, stderr=PIPE
    )
    out, err = new_clone.communicate()

    if new_clone.returncode != 0:
        # Could not clone >< => ABORT
        output += 'FAILED TO CLONE: {}:'.format(out)
        print(output)
        sys.stderr.write(
            '[merge_request_lektor]:clone_repository_fail::{}'.format(err)
        )
        exit(-1)

    output += 'OK |'

    clone_dir = join(tmp_dir, repo_name)

    output += 'Creant virtualenv: {} ... '.format(tmp_dir)
    command = 'mkvirtualenv {}'.format(tmp_dir)
    try:
        new_virtenv = Popen(
            command.split(), cwd=clone_dir, stdout=PIPE, stderr=PIPE
        )
        out, err = new_virtenv.communicate()
        virtenv = new_virtenv.returncode == 0
        if not virtenv:
            output += 'FAILED to create virtualenv, installing on default env |'
        output += 'OK |'
    except OSError as err:
        output += 'FAILED to create virtualenv, installing on default env |'
        virtenv = False
    output += 'Instal.lant dependencies...'
    command = 'pip install -r requirements.txt'
    dependencies = Popen(
        command.split(), cwd=clone_dir, stdout=PIPE, stderr=PIPE
    )
    out, err = dependencies.communicate()
    output += 'OK |'

    # Fem build al directori on tenim la pagina des del directori del clone

    command = 'lektor --project gisce.net-lektor build -O {}'.format(branch_path)
    output += 'Building lektor on {}...'.format(branch_path)
    new_build = Popen(
        command.split(), cwd=clone_dir, stdout=PIPE, stderr=PIPE
    )
    out, err = new_build.communicate()
    if new_build.returncode != 0:
        output += 'FAILED TO BUILD! - Output::{0}'.format(out)
        sys.stderr.write(
            '[merge_request_lektor]:build_lektor_error:{}'.format(err)
        )
        exit(-1)
    output += 'OK |'

    # Creem el directori per /PR/
    command = 'mkdir -p {}'.format(mr_path)
    output += 'Making dir {} ...'.format(mr_path)
    mkdir = Popen(
        command.split(), stdout=PIPE, stderr=PIPE
    )
    out, err = mkdir.communicate()

    # Esborrem el directori per /PR/{id} de possibles copies anteriors
    command = 'rm -r {0}{1}'.format(mr_path, item_id)
    output += 'Removing dir {0}{1} ...'.format(mr_path, item_id)
    rmdir = Popen(
        command.split(), stdout=PIPE, stderr=PIPE
    )
    out, err = rmdir.communicate()

    # Enllaç simbolic per @ amb id

    command = 'ln -s {0} {1}'.format(branch_path, item_id)
    output += 'Symbolic link from data in {0} to {1} ...'.format(
        branch_path, item_id
    )
    sym_link = Popen(
        command.split(), cwd=mr_path, stdout=PIPE, stderr=PIPE
    )
    out, err = sym_link.communicate()
    if sym_link.returncode != 0:
        output += 'FAILED TO SYMLINK! - Output::{0}'.format(out)
        sys.stderr.write(
            '[merge_request_lektor]:sym_link_error:{}'.format(err)
        )
    output += 'OK |'

    try:
        import requests
        # POST /projects/:id/merge_requests/:merge_request_id/notes
        req_url = u'{0}/projects/{1}/merge_requests/{2}/notes'.format(
            http_url, project_id, merge_id
        )
        url_branch = branch_path.split('/', 3)[3]       # Kick out /var/www/
        url_branch = 'www.{}'.format(url_branch)
        url_request = '{0}{1}'.format(mr_path, item_id)
        url_request = url_request.split('/', 3)[3]      # Kick out /var/www/
        url_request = 'www.{}'.format(url_request)
        comment = 'Branch URL: {0}\nPR URL: {1}'.format(url_branch, url_request)
        output += 'Build comment as {} | '.format(comment)
        output += 'POSTing comment to {} ... '.format(req_url)
        token = {'PRIVATE-TOKEN': 'WqrUus2jas9ibFyR5hQp'}
        note = requests.post(req_url, headers=token)
        output += '\n [Response] {} \n'.format(note.status_code)
    except requests.ConnectionError as err:
        sys.stderr.write('Failed to send comment to merge request -'
                         ' Connection [{}]'.format(err))
    except requests.HTTPError as err:
        sys.stderr.write('Failed to send comment to merge request -'
                         ' HTTP [{}]'.format(err))
    except requests.RequestException as err:
        sys.stderr.write('Failed to send comment to merge request -'
                         ' REQUEST [{}]'.format(err))

    if virtenv:
        output += 'Deactivate virtualenv ...'
        command = 'deactivate'
        deact = Popen(
            command, cwd=clone_dir, stdout=PIPE, stderr=PIPE
        )
        out, err = deact.communicate()
        if deact.returncode != 0:
            output += 'FAILED TO DEACTIVATE: {0}::{1}'.format(out, err)
            print(output)
            exit(-1)
        output += 'OK |'

        command = 'rmvirtualenv {}'.format(tmp_dir)
        output += 'Removing virtual environment: {} ...'.format(tmp_dir)
        rm_virt = Popen(
            command.split(), cwd=clone_dir, stdout=PIPE, stderr=PIPE
        )
        out, err = rm_virt.communicate()
        if rm_virt.returncode != 0:
            output += 'FAILED TO REMOVE VIRTUALENV: {0}::{1}'.format(out, err)
            print(output)
            exit(-1)
        output += 'OK |'

print(output)