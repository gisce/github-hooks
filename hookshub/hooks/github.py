# -*- coding: utf-8 -*-
from json import dumps
from os.path import join

from webhook import webhook

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
        super(GitHubWebhook, self).__init__(data)
        self.origin = 'github'

    @property
    def ssh_url(self):
        return self.json['repository']['ssh_url']

    @property
    def http_url(self):
        return self.json['repository']['clone_url']

    @property
    def repo_name(self):
        return self.json['repository']['name']

    @property
    def branch_name(self):
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
                # This is the TARGET branch for the pull-request,
                #  not the source branch
                branch = self.json['pull_request']['base']['ref']

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
    def status(self):
        if self.event == EVENT_STATUS:
            return self.json['state']
        return 'None'

    def get_exe_action(self, action):
        exe_path = join(self.actions_path, action)
        # Action for 'status' event on repository 'powerp-docs'
        if action.startswith('{}-powerp-docs'.format(EVENT_STATUS)):
            json = {}
            json.update({'ssh_url': self.ssh_url})
            json.update({'http_url': self.http_url})
            json.update({'repo-name': self.repo_name})
            json.update({'branch-name': self.branch_name})
            json.update({'state': self.status})
            return [exe_path, dumps(json), self.event]
        elif action.startswith('{}-powerp-docs'.format(EVENT_PUSH)):
            json = {}
            json.update({'ssh_url': self.ssh_url})
            json.update({'http_url': self.http_url})
            json.update({'repo-name': self.repo_name})
            json.update({'branch-name': self.branch_name})
            return [exe_path, dumps(json), self.event]
        else:
            return super(GitHubWebhook, self).get_exe_action(action)

    @property
    def event(self):
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