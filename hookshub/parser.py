# -*- coding: utf-8 -*-
from hookshub.hooks.github import GitHubWebhook as github
from hookshub.hooks.gitlab import GitLabWebhook as gitlab
from multiprocessing import Pool
from osconf import config_from_environment
from hookshub.hooks.webhook import webhook
from subprocess import Popen, PIPE
from os.path import join
import json
import tempfile
import shutil
import logging


class TempDir(object):
    def __init__(self):
        self.dir = tempfile.mkdtemp()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        shutil.rmtree(self.dir)


def run_action(action, hook, conf):
    import os
    logger = logging.getLogger('__main__')
    pid = os.getpid()
    logger.error('[ASYNC({})]Running: {} - {}'.format(pid, action, hook.event))
    args = hook.get_exe_action(action, conf)
    with TempDir() as tmp:
        tmp_path = join(tmp.dir, action)
        with open(tmp_path, 'w') as tmp_json:
            tmp_json.write(args[1])
        args[1] = tmp_path
        proc = Popen(args, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        logger.error('[{}]:ProcOut:\n{}'.format(
            action, stdout.replace('|', '\n')
        ))
        logger.error('[{}]:ProcErr:\n{}'.format(
            action, stderr.replace('|', '\n')
        ))
        returncode = proc.returncode
        if returncode != 0:
            logger.error('[{0}]:Failed!\n'.format(
                action
            ))
        else:
            logger.error('[{0}]:Success!\n'.format(
                action
            ))
    return stdout, stderr, returncode, pid


def log_result(res):
    stdout, stderr, returncode, pid = res
    logger = logging.getLogger('__main__')
    if returncode == 0:
        result = 'Success!'
    else:
        result = 'Failure!'
    logger.error('[ASYNC({})] Result: {}'.format(
        pid, result
    ))


def log_hook_result(res):
    res_code, hook_name = res
    logger = logging.getLogger('__main__')
    if res_code == 0:
        result = 'Success!'
    else:
        result = 'Failure!'
    logger.error('[ASYNC({})] Result: {}'.format(
        hook_name, result
    ))


class HookParser(object):
    def __init__(self, payload_file, event, procs=False):
        self.event = event
        self.payload_file = payload_file
        self.logger = logging.getLogger('__main__')
        self.procs = int(procs)
        self.hook = self.instancer(self.payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        from os import remove
        remove(self.payload_file)

    @property
    def payload(self):
        with open(self.payload_file, 'r') as jsf:
            payload = json.loads(jsf.read())
        return payload

    @staticmethod
    def load_hooks(event=False, repository=False, branch=False):
        from hookshub.hook import get_hooks, reload_hooks
        reload_hooks()
        if event == 'None':
            event = False
        if repository == 'None':
            repository = False
        if branch == 'None':
            branch = False
        return get_hooks(event, repository, branch)

    @staticmethod
    def instancer(payload):
        if 'object_kind' in payload.keys():
            return gitlab(payload)
        elif 'hook' in payload.keys():
            return webhook(payload)
        else:
            return github(payload)

    def run_event_actions(self, def_conf):
        log = ''
        if 'nginx_port' not in def_conf.keys():
            def_conf.update({'nginx_port': '80'})
        if 'action_timeout' not in def_conf.keys():
            def_conf.update({'action_timeout': '30'})
        conf = config_from_environment('HOOKSHUB', [
            'github_token', 'gitlab_token', 'vhost_path', 'nginx_port',
            'action_timeout'
        ], **def_conf)
        timeout = int(conf.get('action_timeout'))
        i = 0
        # Do a pool with specified procs OR a proc for each action
        procs = self.procs or len(self.hook.event_actions)
        if not procs:
            # If no tasks to do → do nothing
            return 0, log
        if self.logger:
            self.logger.error('Executing {} actions for event: {}\n'.format(
                len(self.hook.event_actions), self.hook.event
            ))
            self.logger.info('Running actions on {} processes'.format(
                procs
            ))
        pool = Pool(processes=procs)
        for action in self.hook.event_actions:
            i += 1
            if self.logger:
                self.logger.error('[Running: <{0}/{1}> - {2}]\n'.format(
                    i, len(self.hook.event_actions), action)
                )
            proc = pool.apply_async(
                run_action, args=(action, self.hook, conf),
                callback=log_result
            )
            proc.wait(timeout=timeout)
            if proc.ready():
                stdout, stderr, returncode, pid = proc.get()
            else:
                stdout = stderr = 'Still running async, but answering.' \
                                  ' Check log for detailed result...'
                self.logger.error('[{}]:{}'.format(action, stderr))
                returncode = 0

            output = ''
            output += ('[{0}]:ProcOut:\n{1}'.format(
                action, stdout
            ))
            output += ('[{0}]:ProcErr:\n{1}'.format(
                action, stderr
            ))
            if returncode and returncode != 0:
                log += ('[{0}]:{1}\n[{0}]:Failed!\n'.format(
                    action, output
                ))
                return -1, log
            log += ('[{0}]:{1}\n[{0}]:Success!\n'.format(
                action, output
            ))

        return 0, log

    def run_event_hooks(self, def_conf):
        log = ''
        if 'nginx_port' not in def_conf.keys():
            def_conf.update({'nginx_port': '80'})
        if 'action_timeout' not in def_conf.keys():
            def_conf.update({'action_timeout': '10'})
        conf = config_from_environment('HOOKSHUB', [
            'github_token', 'gitlab_token', 'vhost_path', 'nginx_port',
            'action_timeout'
        ], **def_conf)
        timeout = int(conf.get('action_timeout'))
        i = 0
        hooks = self.load_hooks(
            self.hook.event, self.hook.repo_name, self.hook.branch_name
        )
        # Do a pool with specified procs OR a proc for each action
        procs = self.procs or len(self.hook.event_actions)
        if not procs:
            # If no tasks to do → do nothing
            return 0, log
        if self.logger:
            self.logger.error('Executing {} hooks for event: {}\n'.format(
                len(hooks), self.hook.event
            ))
            self.logger.info('Running actions on {} processes'.format(
                procs
            ))
        pool = Pool(processes=procs)
        for action_name, action in hooks:
            i += 1
            if self.logger:
                self.logger.error('[Running: <{0}/{1}> - {2}]\n'.format(
                    i, len(hooks), action_name)
                )
            args = action.get_args(self.hook, conf)
            proc = pool.apply_async(
                action.run_hook, args=(args,),
                callback=log_hook_result
            )
            proc.wait(timeout=timeout)
            if proc.ready():
                returncode, hook_name = proc.get()
            else:
                strerr = 'Still running async, but answering.' \
                                  ' Check log for detailed result...'
                self.logger.error('[{}]:{}'.format(action.title, strerr))
                returncode = 0

            if returncode and returncode != 0:
                log += ('[{0}]:Failed!\n'.format(
                    action_name
                ))
                return -1, log
            log += ('[{0}]:Success!\n'.format(
                action_name
            ))

        return 0, log
