# -*- coding: utf-8 -*-
from json import dumps, loads
from os.path import join, isfile
from subprocess import Popen, PIPE
from hookshub.hooks.webhook import webhook

import requests
import polib
import sys

# GitHub Events
# For more info, see: https://developer.github.com/v3/activity/events/types/

COMMIT_COMMENT = 'commit_comment'
EVENT_CREATE = 'create'
EVENT_DELETE = 'delete'
EVENT_DEPLOYMENT = 'deployment'
DEPLOYMENT_STATUS = 'deployment_status'
EVENT_FORK = 'fork'
EVENT_WIKI = 'gollum'
ISSUE_COMMENT = 'issue_comment'
EVENT_ISSUE = 'issues'
EVENT_MEMBER = 'member'
EVENT_MEMBERSHIP = 'membership'
EVENT_PAGE_BUILD = 'page_build'
PUBLIC_EVENT = 'public'
PULL_REQUEST = 'pull_request'
REVIEW_PR_COMMENT = 'pull_request_review_comment'
EVENT_PUSH = 'push'
EVENT_RELEASE = 'release'
EVENT_REPOSITORY = 'repository'
EVENT_STATUS = 'status'
EVENT_TEAM_ADD = 'team_add'
EVENT_WATCH = 'watch'


class GitHubWebhook(webhook):

    def __init__(self, data):
        """
        :param data: Data loaded from the JSON of the hook's
            payload served by GitHub
            :type: Dictionary
        """
        super(GitHubWebhook, self).__init__(data)
        self.origin = 'github'

    @property
    def ssh_url(self):
        """
        :return: Repository's ssh url
        :rtype: String
        """
        return self.json['repository']['ssh_url']

    @property
    def http_url(self):
        """
        :return: Repository's http url
        :rtype: String
        """
        return self.json['repository']['clone_url']

    @property
    def repo_name(self):
        """
        :return: Repository's name
        :rtype: String
        """
        return self.json['repository']['name']

    @property
    def branch_name(self):
        """
        :return: Branch name used on the hook's event, it can be None
            if the event doesn't use one. If the branch is going to be gotten
            from a PR's hook, it gets the SOURCE branch.
        :rtype: String
        """
        branch = 'None'
        try:
            # Case 1: a ref_type indicates the type of ref.
            # This true for create and delete events.
            if self.event in [EVENT_CREATE, EVENT_DELETE]:
                if self.json['ref_type'] == 'branch':
                    branch = self.json['ref']
            # Case 2: a pull_request object is involved.
            # This is pull_request and pull_request_review_comment events.
            elif self.event in [PULL_REQUEST, REVIEW_PR_COMMENT]:
                # This is the SOURCE branch for the pull-request,
                #  not the source branch
                branch = self.json['pull_request']['head']['ref']

            elif self.event in [EVENT_PUSH]:
                # Push events provide a full Git ref in 'ref' and
                #  not a 'ref_type'.
                branch = self.json['ref'].split('/')[2]

        except KeyError:
            # If the self.json structure isn't what we expect,
            #  we'll live without the branch name
            pass
        return branch

    @property
    def target_branch_name(self):
        """
        :return: TARGET branch name from a PR's hook
        :rtype: String
        """
        # Get TARGET branch from pull request
        if self.event in [PULL_REQUEST, REVIEW_PR_COMMENT]:
            return self.json['pull_request']['base']['ref']
        return 'None'

    @property
    def status(self):
        """
        :return: State from the hook of an status event
        :rtype: String
        """
        if self.event == EVENT_STATUS:
            return self.json['state']
        return 'None'

    @property
    def action(self):
        """
        :return: Action from the hook of a PR event
        :rtype: String
        """
        if self.event == PULL_REQUEST:
            return self.json['action']
        return 'None'

    @property
    def number(self):
        """
        :return: Number (id) of the PR/Issue
        :rtype: Int
        """
        if self.event == PULL_REQUEST:
            return self.json['number']
        elif self.event == REVIEW_PR_COMMENT:
            return self.json['pull_request']['number']
        elif self.event in [EVENT_ISSUE, ISSUE_COMMENT]:
            return self.json['issue']['number']
        else:
            return 'None'

    @property
    def repo_id(self):
        """
        :return: ID of the repository
        :rtype: Int
        """
        return self.json['repository']['id']

    @property
    def repo_full_name(self):
        """
        :return: Full name of the repository. It have the onwer name within it.
        :rtype: String
        """
        return self.json['repository']['full_name']

    @property
    def merged(self):
        """
        :return: Gets the merged state of a PR from the hook's payload
        :rtype: Bool
        """
        if self.event == PULL_REQUEST:
            return self.json['pull_request']['merged']
        return False

    def get_exe_action(self, action, conf):
        """
        :param action: event to get the scripts
            :type: String
        :param conf: Dictionary with the environment configurations
            :type: Dictionary
        :return: A list with the path to the scripts, the params they need
            and the event used
        """
        exe_path = join(self.actions_path, action)
        json = {}
        # Action for 'push', 'pull_request' event
        #       on repository 'powerp-docs'
        if action.startswith('{}-powerp-docs'.format(EVENT_PUSH)) or\
                action.startswith('{}-powerp-docs'.format(PULL_REQUEST)):
            json.update({'token': conf['github_token']})
            json.update({'vhost_path': conf['vhost_path']})
            json.update({'port': conf['nginx_port']})
            json.update({'ssh_url': self.ssh_url})
            json.update({'http_url': self.http_url})
            json.update({'repo_name': self.repo_name})
            json.update({'repo_full_name': self.repo_full_name})
            json.update({'branch_name': self.branch_name})

            # If 'pull_request' event, we may add more params
            if action.startswith('{}-powerp-docs'.format(PULL_REQUEST)):
                json.update({'action': self.action})
                json.update({'number': self.number})

            # Return the params
            return [exe_path, dumps(json), self.event]
        else:
            return super(GitHubWebhook, self).get_exe_action(action, conf)

    @property
    def event(self):
        """
        :return: The GitHub event type decoded from the JSON payload (data attr)
        :rtype: String
        """
        if 'commits' in self.json.keys():
            return 'push'

        elif 'master_branch' in self.json.keys():
            return 'create'

        elif 'ref_type' in self.json.keys():
            # This case must be under 'create'
            #   as it also has the 'ref_type' field on the payload
            return 'delete'

        elif 'deployment_status' in self.json.keys():
            return 'deployment_status'

        elif 'deployment' in self.json.keys():
            # This case must be under 'deployment_status'
            #   as it also has the 'deployment' field on the payload
            return 'deployment'

        elif 'forkee' in self.json.keys():
            return 'fork'

        elif 'pages' in self.json.keys():
            return 'gollum'

        elif 'issue' in self.json.keys():
            return ('issue_comment'
                    if self.json['action'] == 'created'
                    else 'issues')

        elif 'scope' in self.json.keys():
            return 'membership'

        elif 'build' in self.json.keys():
            return 'page_build'

        elif 'member' in self.json.keys():
            return 'member'

        elif 'comment' in self.json.keys():
            return ('pull_request_review_comment'
                    if 'pull_request' in self.json.keys()
                    else 'commit_comment'
                    )

        elif 'pull_request' in self.json.keys():
            return 'pull_request'

        elif 'release' in self.json.keys():
            return 'release'

        elif 'state' in self.json.keys():
            return 'status'

        elif 'team' in self.json.keys():
            # membership also uses 'team' in payload,
            # so this case may be under that case
            return 'team_add'

        elif 'organization' in self.json.keys():
            return 'repository'

        elif 'action' in self.json.keys():
            # Some other events use 'action' on its payload, so this case
            #   must be almost at the end where it's the last one to use it
            return 'watch'

        else:
            # As it has no specific payload, this one may be the last one
            return 'public'

    @property
    def event_actions(self):
        """
        :return: All the scripts that match with the event decoded
        :rtype: List<String>
        """
        # We start with all actions that start with {event}
        # Then we filter them to not execute the actions for the same event
        #  with different repository.
        # Finally we filter what's left to not execute actions with the same
        #  repository but different branches
        events = super(GitHubWebhook, self).event_actions
        events = [
            event
            for event in events
            # If they start with {event}-{repository}-{branch}
            if event.startswith('{0}-{1}-{2}'.format(
                self.event, self.repo_name, self.branch_name
            )) or
            # If they start with {event}-{repository}_{name}
            event.startswith('{0}-{1}_'.format(self.event, self.repo_name)) or
            # If they are named after {event}-{repository}
            event == '{0}-{1}.py'.format(self.event, self.repo_name) or
            # If they start with {event}_{name}
            event.startswith('{0}_'.format(self.event)) or
            # If they are named after {event}
            event == '{0}.py'.format(self.event)
        ]
        return events


class GitHubUtil:
    @staticmethod
    def clone_on_dir(dir, branch, repository, url):
        """
        :param dir: Directory where the clone will be applied. This may exist
            or it'll throw an exception.
            :type: String
        :param branch: Branch to clone from the repository. If cloning master,
            this may have the value 'None'
            :type: String
        :param repository: Repository to clone from. Cannot be None
            :type: String
        :param url: URL used to clone the repository
            :type: String
        :return: Returns the log output, the return code from the clone and the
            clone error log.
            :rtype: Tuple<String,Int,String>
        """
        output = "Clonant el repositori '{}'".format(repository)
        command = 'git clone {}'.format(url)
        if branch != 'None':
            output += ", amb la branca '{}'".format(branch)
            command += ' --branch {}'.format(branch)
            output += ' ... '
        new_clone = Popen(
            command.split(), cwd=dir, stdout=PIPE, stderr=PIPE
        )
        out, err = new_clone.communicate()
        if new_clone.returncode != 0:
            output += 'FAILED TO CLONE: {}: | ' \
                      'Try to clone from https ...'.format(out)
            err = ':clone_repository_fail::{}'.format(err)
        return output, new_clone.returncode, err

    @staticmethod
    def pip_requirements(dir):
        """
        Installs all the requirements from the requirements.txt in the specified
        directory. If no virtualenv is set previously for the Popen, they will
        be installed in the user's python directory
        :param dir: Directory where the requirements.txt is found. Used to call
            Popen with the pip install.
            :type: String
        :return: Output with the log. Does not include any of the pip install
            output or error prints.
        :rtype: String
        """
        output = 'Instal.lant dependencies...'
        command = 'pip install -r requirements.txt'
        dependencies = Popen(
            command.split(), cwd=dir, stdout=PIPE, stderr=PIPE
        )
        out, err = dependencies.communicate()
        if dependencies.returncode != 0:
            output += ' Couldn\'t install all dependencies '
        return output

    @staticmethod
    def export_pythonpath(docs_path):
        """
        :param docs_path: Path to the docs clone. Must have the sitecustomize
            directory, as that's what the $PYTHONPATH will point to
            :type:  String
        :return: An output log saying if everything was ok
        """
        sc_path = join(docs_path, 'sitecustomize')
        command = 'export PYTHONPATH={}'.format(sc_path)
        try:
            export = Popen(
                command.split(), cwd=docs_path, stdout=PIPE, stderr=PIPE
            )
            if export.returncode == 0:
                output = 'Success to export sitecustomize path'
            else:
                output = 'Failed to export sitecustomize path'
        except Exception as err:
            output = 'Failed to export sitecustomize path'
        return output

    @staticmethod
    def build_mo_file(dir, lang='es_ES'):
        """
        Build a mo file from a pofile in the designed directory path.
         It does use the specified lang to choose the path to use.
         Uses default localization path.
        :param dir: Base path from which the po file must be found
            :type: String
        :param lang: Language to be build, used on po-file path
            :type: String
        :return: True if built successfully, False if errors found.
        """
        podir = join(
            dir,
            join(
                'locales',
                join(
                    lang,
                    'LC_MESSAGES'
                )
            )
        )
        try:
            po = polib.pofile(join(podir, 'message.po'))
            po.save_as_mofile(join(podir, 'messages.mo'))
            return True
        except Exception as err:
            return False

    @staticmethod
    def docs_build(dir, target=None, file=None, clean=True):
        """
        :param dir: Directory used to call the build. This MUST exist.
            :type:  String
        :param target: Directory to build to. If not set or None, the target
            build is the default one, that is the same as 'dir'
            :type:  String
        :param clean: Defines if the '--clean' tag is used or not. If true,
            this cleans the directory before the build.
            :type:  Bool
        :return: An output log with some annotations and the output and error
            log from the mkdocs build call. And a String containing the path
            where the docs have been built
            :type: Tuple<String, String>
        """
        build_path = dir
        output = 'Building mkdocs from {} '.format(dir)
        command = 'mkdocs build'
        if target:
            build_path = target
            output += 'to {}...'.format(target)
            command += ' -d {}'.format(target)
        if file:
            output += ' using file config file "{}"...'.format(file)
            command += ' -f {}'.format(file)
        if clean:
            command += ' --clean'
        try:
            new_build = Popen(
                command.split(), cwd=dir, stdout=PIPE, stderr=PIPE
            )
            out, err = new_build.communicate()
            if new_build.returncode != 0:
                output += 'FAILED TO BUILD: {0}::{1}'.format(out, err)
                return output, False
        except Exception as err:
            output += 'Build Failed with exception from Popen... {}'.format(err)
            return output, False

        return output, build_path

    @staticmethod
    def get_pr(token, repository, branch):
        """
        :param token: The token from GitHub to use on the HTTP Request
            :type:  String
        :param repository: The source repository to get the PR
            :type:  String
        :param branch: The source branch used by the PR in the repository
            :type:  String
        :return: Returns the Pull Request JSON data for the PR
        :rtype: String
        """
        output = 'Getting pull request... '
        if not repository or not branch:
            output += 'Repository and branch needed to get pull request!'
            return -1, output
        github_api_url = "https://api.github.com"
        auth_token = 'token {}'.format(token)
        head = {'Authorization': auth_token}
        # GET / repos / {:owner / :repo} / pulls
        req_url = '{0}/repos/{1}/pulls'.format(
            github_api_url, repository
        )
        code = -1
        try:
            pulls = requests.get(req_url, headers=head)
            if pulls.status_code != 200:
                output += 'OMITTING |'
                raise Exception('Could Not Get PULLS')
            prs = loads(pulls.text)
            # There are only opened PR, so the one that has the same branch name
            #   is the one we are looking for
            my_prs = [pr for pr in prs if pr['head']['ref'] == branch]
            if my_prs:
                code = my_prs[0]
                output += 'MyPr: {}'.format(code['number'])
            else:
                output += 'OMITTING |'
                raise Exception('Could Not Get PULLS')
        except requests.ConnectionError as err:
            output = 'Failed to send comment to pull request -' \
                     ' Connection [{}]'.format(err)
        except requests.HTTPError as err:
            output = 'Failed to send comment to pull request -' \
                             ' HTTP [{}]'.format(err)
        except requests.RequestException as err:
            output = 'Failed to send comment to pull request -' \
                             ' REQUEST [{}]'.format(err)
        except Exception as err:
            output = 'Failed to send comment to pull request, ' \
                             'INTERNAL ERROR [{}]'.format(err)
        return code, output

    @staticmethod
    def post_comment_pr(token, repository, pr_num, message):
        """
        :param token:   GitHub Token used for the HTTP Requests
            :type:  String
        :param repository: The repository where the PR belongs to
            :type:  String
        :param pr_num: The PR number or ID for which we may send the comment
            :type:  Int
        :param message: The message to write the comment
            :type:  String
        :return: The HTTP Response's status code. If it works well, this may
            return the status code 201 (Created). If it doesn't, this may
            return the code 0 along with a text with the error found.
        :rtype: Tuple<Int,String>
        """
        github_api_url = "https://api.github.com"
        # POST /repos/{:owner /:repo}/issues/{:pr_id}/comments
        req_url = '{0}/repos/{1}/issues/{2}/comments'.format(
            github_api_url, repository, pr_num
        )
        auth_token = 'token {}'.format(token)
        head = {'Authorization': auth_token}
        payload = {'body': message}
        code = 0
        try:
            post = requests.post(req_url, headers=head, json=payload)
            code = post.status_code
            text = post.text
            if code != 201:
                raise Exception(
                    "Bad return code, returned text: \n[{}]\n".format(
                        text
                    )
                )
        except requests.ConnectionError as err:
            text = 'Failed to send comment to pull request -' \
                             ' Connection [{}]'.format(err)
        except requests.HTTPError as err:
            text = 'Failed to send comment to pull request -' \
                             ' HTTP [{}]'.format(err)
        except requests.RequestException as err:
            text = 'Failed to send comment to pull request -' \
                             ' REQUEST [{}]'.format(err)
        except Exception as err:
            text = 'Failed to send comment to pull request, ' \
                             'INTERNAL ERROR [{}]'.format(err)
        return code, text
