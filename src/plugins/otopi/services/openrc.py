#
# otopi -- plugable installer
#


"""OpenRC services provider"""


import gettext
import os


from otopi import constants
from otopi import plugin
from otopi import services
from otopi import util


def _(m):
    return gettext.dgettext(message=m, domain='otopi')


@util.export
class Plugin(plugin.PluginBase, services.ServicesBase):
    """OpenRC services provider"""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('rc')
        self.command.detect('rc-update')

    @plugin.event(
        stage=plugin.Stages.STAGE_PROGRAMS,
        after=(
            constants.Stages.SYSTEM_COMMAND_DETECTION,
        ),
    )
    def _programs(self):
        rc = self.command.get('rc', optional=True)
        if rc is not None:
            (ret, stdout, stderr) = self.execute(
                (rc, '--version'),
                raiseOnError=False,
            )
            if ret == 0 and len(stdout) == 1 and 'OpenRC' in stdout[0]:
                self.logger.debug('registering OpenRC provider')
                self.context.registerServices(services=self)

    #
    # ServicesBase
    #

    def _getServiceScript(self, name):
        return os.path.join('/etc/init.d', name)

    def _executeServiceCommand(self, name, command, raiseOnError=True):
        return self.execute(
            (self._getServiceScript(name), '-q', command),
            raiseOnError=raiseOnError
        )

    @property
    def setSupportsDependency(self):
        return True

    def exists(self, name):
        self.logger.debug('check if service %s exists', name)
        return os.path.exists(self._getServiceScript(name))

    def status(self, name):
        self.logger.debug('check service %s status', name)
        rc, stdout, stderr = self._executeServiceCommand(
            name,
            'status',
            raiseOnError=False
        )
        return rc == 0

    def startup(self, name, state):
        self.logger.debug('set service %s startup to %s', name, state)
        self.execute(
            (
                self.command.get('rc-update'),
                'add' if state else 'del',
                name
            ),
            raiseOnError=False,
        )

    def state(self, name, state):
        self.logger.debug(
            '%s service %s',
            'starting' if state else 'stopping',
            name
        )
        rc, stdout, stderr = self._executeServiceCommand(
            name,
            'start' if state else 'stop',
            raiseOnError=False,
        )
        if rc != 0:
            raise RuntimeError(
                _("Failed to {do} service '{service}'").format(
                    do=_('start') if state else _('stop'),
                    service=name,
                )
            )


# vim: expandtab tabstop=4 shiftwidth=4
