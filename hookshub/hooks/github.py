# -*- coding: utf-8 -*-
from json import dumps, loads
from os.path import join, isfile, isdir
from subprocess import Popen, PIPE
from hookshub.hooks.webhook import webhook

import requests
import os

# GitHub Events
# For more info, see: https://developer.github.com/v3/activity/events/types/


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
            if self.event in [GitHubUtil.events['EVENT_CREATE'],
                              GitHubUtil.events['EVENT_DELETE']]:
                if self.json['ref_type'] == 'branch':
                    branch = self.json['ref']
            # Case 2: a pull_request object is involved.
            # This is pull_request and pull_request_review_comment events.
            elif self.event in [
                GitHubUtil.events['EVENT_PULL_REQUEST'],
                GitHubUtil.events['EVENT_PULL_REQUEST_REVIEW'],
                GitHubUtil.events['EVENT_REVIEW_PR_COMMENT']
            ]:
                # This is the SOURCE branch for the pull-request,
                #  not the source branch
                branch = self.json['pull_request']['head']['ref']

            elif self.event in [GitHubUtil.events['EVENT_PUSH']]:
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
        if self.event in [GitHubUtil.events['EVENT_PULL_REQUEST'],
                          GitHubUtil.events['EVENT_REVIEW_PR_COMMENT']]:
            return self.json['pull_request']['base']['ref']
        return 'None'

    @property
    def status(self):
        """
        :return: State from the hook of an status event
        :rtype: String
        """
        if self.event == GitHubUtil.events['EVENT_STATUS']:
            return self.json['state']
        return 'None'

    @property
    def action(self):
        """
        :return: Action from the hook of a PR event
        :rtype: String
        """
        if self.event == GitHubUtil.events['EVENT_PULL_REQUEST']:
            return self.json['action']
        return 'None'

    @property
    def number(self):
        """
        :return: Number (id) of the PR/Issue
        :rtype: Int
        """
        if self.event == GitHubUtil.events['EVENT_PULL_REQUEST']:
            return self.json['number']
        elif self.event in [
            GitHubUtil.events['EVENT_REVIEW_PR_COMMENT'],
            GitHubUtil.events['EVENT_PULL_REQUEST_REVIEW']
        ]:
            return self.json['pull_request']['number']
        elif self.event in [GitHubUtil.events['EVENT_ISSUE'],
                            GitHubUtil.events['EVENT_ISSUE_COMMENT']]:
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
        From: https://developer.github.com/v3/activity/events/types/#pullrequestevent
        If the action is "closed" and the merged key is true,
          the pull request was merged.
        :return: Gets the merged state of a PR from the hook's payload
        :rtype: Bool
        """
        if self.event == GitHubUtil.events['EVENT_PULL_REQUEST']:
            return self.json['pull_request']['merged'] == True
        return False

    @property
    def closed(self):
        """
        From: https://developer.github.com/v3/activity/events/types/#pullrequestevent
         If the action is "closed" and the merged key is false,
         the pull request was closed with unmerged commits.
         If the action is "closed" and the merged key is true,
         the pull request was merged
        As the action can be obtained from the 'action' property, we use this
        property to know if it closed but not merged.
        :return: True when the action of the PR is 'closed' and not 'merged'
        :rtype: Bool
        """
        if self.event == GitHubUtil.events['EVENT_PULL_REQUEST']:
            if self.json['action'] == GitHubUtil.actions['ACT_CLOSED']:
                return not self.merged
        return False

    @property
    def event(self):
        """
        :return: The GitHub event type decoded from the JSON payload (data attr)
        :rtype: String
        """
        if 'commits' in self.json.keys():
            return GitHubUtil.events['EVENT_PUSH']

        elif 'master_branch' in self.json.keys():
            return GitHubUtil.events['EVENT_CREATE']

        elif 'ref_type' in self.json.keys():
            # This case must be under 'create'
            #   as it also has the 'ref_type' field on the payload
            return GitHubUtil.events['EVENT_DELETE']

        elif 'deployment_status' in self.json.keys():
            return GitHubUtil.events['EVENT_DEPLOYMENT_STATUS']

        elif 'deployment' in self.json.keys():
            # This case must be under 'deployment_status'
            #   as it also has the 'deployment' field on the payload
            return GitHubUtil.events['EVENT_DEPLOYMENT']

        elif 'forkee' in self.json.keys():
            return GitHubUtil.events['EVENT_FORK']

        elif 'pages' in self.json.keys():
            return GitHubUtil.events['EVENT_WIKI']

        elif 'issue' in self.json.keys():
            return (GitHubUtil.events['EVENT_ISSUE_COMMENT']
                    if self.json['action'] == GitHubUtil.actions['ACT_CREATED']
                    else GitHubUtil.events['EVENT_ISSUE'])

        elif 'scope' in self.json.keys():
            return GitHubUtil.events['EVENT_MEMBERSHIP']

        elif 'build' in self.json.keys():
            return GitHubUtil.events['EVENT_PAGE_BUILD']

        elif 'member' in self.json.keys():
            return GitHubUtil.events['EVENT_MEMBER']

        elif 'comment' in self.json.keys():
            return (GitHubUtil.events['EVENT_REVIEW_PR_COMMENT']
                    if 'pull_request' in self.json.keys()
                    else GitHubUtil.events['EVENT_COMMIT_COMMENT']
                    )

        elif 'pull_request' in self.json.keys():
            if 'review' in self.json.keys():
                return GitHubUtil.events['EVENT_PULL_REQUEST_REVIEW']
            return GitHubUtil.events['EVENT_PULL_REQUEST']

        elif 'release' in self.json.keys():
            return GitHubUtil.events['EVENT_RELEASE']

        elif 'state' in self.json.keys():
            return GitHubUtil.events['EVENT_STATUS']

        elif 'team' in self.json.keys():
            # membership also uses 'team' in payload,
            # so this case may be under that case
            return GitHubUtil.events['EVENT_TEAM_ADD']

        elif 'organization' in self.json.keys():
            return GitHubUtil.events['EVENT_REPOSITORY']

        elif 'action' in self.json.keys():
            # Some other events use 'action' on its payload, so this case
            #   must be almost at the end where it's the last one to use it
            return GitHubUtil.events['EVENT_WATCH']

        else:
            # As it has no specific payload, this one may be the last one
            return GitHubUtil.events['EVENT_PUBLIC_EVENT']


class GitHubUtil:

    api_url = 'https://api.github.com'

    actions = {
        'ACT_ASSIGNED': 'assigned',
        'ACT_UNASSIGN': 'unassigned',
        'ACT_LABELED': 'labeled',
        'ACT_UNLABELED': 'unlabeled',
        'ACT_OPENED': 'opened',
        'ACT_EDITED': 'edited',
        'ACT_CLOSED': 'closed',
        'ACT_REOPENED': 'reopened',
        'ACT_SYNC': 'synchronize',
        'ACT_CREATED': 'created'
    }

    events = {
        'EVENT_COMMIT_COMMENT': 'commit_comment',
        'EVENT_CREATE': 'create',
        'EVENT_DELETE': 'delete',
        'EVENT_DEPLOYMENT': 'deployment',
        'EVENT_DEPLOYMENT_STATUS': 'deployment_status',
        'EVENT_FORK': 'fork',
        'EVENT_WIKI': 'gollum',
        'EVENT_ISSUE_COMMENT': 'issue_comment',
        'EVENT_ISSUE': 'issues',
        'EVENT_MEMBER': 'member',
        'EVENT_MEMBERSHIP': 'membership',
        'EVENT_PAGE_BUILD': 'page_build',
        'EVENT_PUBLIC_EVENT': 'public',
        'EVENT_PULL_REQUEST': 'pull_request',
        'EVENT_PULL_REQUEST_REVIEW': 'pull_request_review_comment',
        'EVENT_REVIEW_PR_COMMENT': 'pull_request_review_comment',
        'EVENT_PUSH': 'push',
        'EVENT_RELEASE': 'release',
        'EVENT_REPOSITORY': 'repository',
        'EVENT_STATUS': 'status',
        'EVENT_TEAM_ADD': 'team_add',
        'EVENT_WATCH': 'watch'
    }

    @staticmethod
    def clone_on_dir(dir, repository, url, branch=None):
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
        if branch and branch != 'None':
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
        github_api_url = GitHubUtil.api_url
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
