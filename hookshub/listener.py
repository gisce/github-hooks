# -*- coding: utf-8 -*-
from hookshub.hooks.github import GitHubWebhook as github
from hookshub.hooks.gitlab import GitLabWebhook as gitlab
from osconf import config_from_environment
from hookshub.hooks.webhook import webhook
from subprocess import Popen, PIPE
from os.path import join
from datetime import datetime
import json
import tempfile
import shutil


class TempDir(object):
    def __init__(self):
        self.dir = tempfile.mkdtemp()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        shutil.rmtree(self.dir)


class HookListener(object):
    def __init__(self, payload_file, event):
        self.event = event
        self.payload = {}
        with open(payload_file, 'r') as jsf:
            self.payload = json.loads(jsf.read())
        import logging
        self.logger = logging.getLogger('__main__')

    @staticmethod
    def instancer(payload):
        if 'object_kind' in payload.keys():
            return gitlab(payload)
        elif 'hook' in payload.keys():
            return webhook(payload)
        else:
            return github(payload)

    def run_event_actions(self, config_file):
        def_conf = {}
        log = ''
        
        with open(config_file, 'r') as config:
            def_conf = json.loads(config.read())

        if not 'nginx_port' in def_conf.keys():
            def_conf.update({'nginx_port': '80'})
            
        conf = config_from_environment('HOOKSHUB', [
            'github_token', 'gitlab_token', 'vhost_path', 'nginx_port'
        ], **def_conf)

        hook = self.instancer(self.payload)
        i = 0

        if self.logger:
            self.logger.info('{} Executing {} actions\n'.format(
                datetime.now().strftime('[%d/%m/%Y-%H:%M:%S]'),
                len(hook.event_actions))
            )

        for action in hook.event_actions:
            i += 1
            if self.logger:
                self.logger.info('{0}[Running: <{1}/{2}> - {3}]\n'.format(
                    datetime.now().strftime('[%d/%m/%Y-%H:%M:%S]'),
                    i, len(hook.event_actions), action)
                )
            args = hook.get_exe_action(action, conf)
            with TempDir() as tmp:
                tmp_path = join(tmp.dir, action)
                with open(tmp_path, 'w') as tmp_json:
                    tmp_json.write(args[1])
                args[1] = tmp_path
                proc = Popen(args, stdout=PIPE, stderr=PIPE)
                stdout, stderr = proc.communicate()
                output = ''
                output += ('[{0}]:ProcOut:\n{1}'.format(
                    action, stdout
                ))
                output += ('[{0}]:ProcErr:\n{1}'.format(
                    action, stderr
                ))
                if proc.returncode != 0:
                    log = ('{0}[{1}]:{2}\n[{1}]:Failed!\n'.format(
                        datetime.now().strftime('[%d/%m/%Y-%H:%M:%S]'),
                        action, output
                    ))
                    self.logger.error(log.replace('|', '\n'))
                    return -1, log
                log = ('{0}[{1}]:{2}\n[{1}]:Success!\n'.format(
                    datetime.now().strftime('[%d/%m/%Y-%H:%M:%S]'),
                    action, output
                ))
                self.logger.info(log.replace('|', '\n'))
        return 0, log
