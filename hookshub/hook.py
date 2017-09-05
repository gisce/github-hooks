from pkg_resources import iter_entry_points
import logging


class Hook(object):
    """
    This class is used as a template for hook import as a plugin.
    All the methods can be overwritten but the super's __init__ must run inside
    __init__

    Enable may configure alternative parameters for the hook to run, that's why
    initiates at False and runs enable() on __init__
    """
    def __init__(self, method, event=False, repository=False, branch=False):
        self._name = str(self.__class__)
        self._hook = method
        self._event = event
        self._repository = repository
        self._branch = branch
        self._enabled = False
        self.enable()

    def is_enabled(self):
        return self._enabled

    def get_args(self, webhook, conf):
        """
        :param webhook: WebHook with origin's payload
        :param conf: environment conf to be used
        :return: Args to call "run_hook" method
        """
        return {}

    def enable(self):
        self._enabled = True
        return self.is_enabled()

    def disable(self):
        self._enabled = False
        return self.is_enabled()

    def run_hook(self, args=False):
        if not args:
            raise EnvironmentError(
                'Args for hook {} were not set before running'.format(
                    self.title
                )
            )
        return self._hook(args), self.title

    @property
    def title(self):
        return self._name

    @property
    def hook(self):
        return self._hook

    @property
    def event(self):
        return self._event

    @property
    def repository(self):
        return self._repository

    @property
    def branch(self):
        return self._branch

    @property
    def enabled(self):
        return self._enabled


#
# Using Hooks Manager (hookshub.plugins) a hook may be disabled or enabled
#
# With "reload_hooks()" the hooks are reloaded with no need to
# restart the service
#
# "get_hooks()" must return all hooks loaded
#


def get_hooks(event=False, repository=False, branch=False):
    from hookshub.plugins import plugins
    results = []
    hooks = plugins.get_hooks()
    for hook in hooks:
        if event and hook.event:
            ev = hook.event == event
        else:
            ev = True
        if repository and hook.repository:
            repo = hook.repository == repository
        else:
            repo = True
        if branch and hook.branch:
            br = hook.branch == branch
        else:
            br = True
        if ev and repo and br:
            results.append((hook.name, hook.hook))
    return results


def reload_hooks():
    from hookshub.plugins import plugins
    logger = logging.getLogger()
    for entrypoint in set(iter_entry_points('hookshub.plugins')):
        try:
            plugin = entrypoint.load()
        except Exception as e:
            logger.error('Could not load plugin {}:\n{}'.format(
                entrypoint, e
            ))
        else:
            plugins.register(plugin)