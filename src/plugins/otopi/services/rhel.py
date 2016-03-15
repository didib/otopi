#
# otopi -- plugable installer
#


"""rhel services provider."""


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
    """rhel services provider."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('service')
        self.command.detect('chkconfig')
        self.command.detect('systemctl')
        self.command.detect('initctl')

    @plugin.event(
        stage=plugin.Stages.STAGE_PROGRAMS,
        after=(
            constants.Stages.SYSTEM_COMMAND_DETECTION,
        ),
    )
    def _programs(self):
        haveSystemd = False
        systemctl = self.command.get('systemctl', optional=True)
        if systemctl is not None:
            (ret, stdout, stderr) = self.execute(
                (systemctl, 'show-environment'),
                raiseOnError=False,
            )
            if ret == 0:
                haveSystemd = True

        if (
            not haveSystemd and
            self.command.get('service', optional=True) is not None
        ):
            self.logger.debug('registering rhel provider')
            self.context.registerServices(services=self)

    #
    # ServicesBase
    #

    def _executeInitctlCommand(self, name, command, raiseOnError=True):
        return self.execute(
            (
                self.command.get('initctl'),
                command,
                name,
            ),
            raiseOnError=raiseOnError
        )

    def _executeServiceCommand(self, name, command, raiseOnError=True):
        return self.execute(
            (
                self.command.get('service'),
                name,
                command
            ),
            raiseOnError=raiseOnError
        )

    def _isUpstart(self, name):
        exists = False
        status = False

        if self.command.get('initctl') is not None:
            #
            # status always returns rc 0 no mater
            # what state it is
            #
            rc, stdout, stderr = self._executeInitctlCommand(
                name,
                'status',
                raiseOnError=False,
            )
            if rc == 0 and len(stdout) == 1:
                exists = True
                if 'start/' in stdout[0]:
                    status = True
        return (exists, status)

    def exists(self, name):
        ret = False
        self.logger.debug('check if service %s exists', name)
        (upstart, status) = self._isUpstart(name)
        if upstart:
            ret = True
        else:
            ret = os.path.exists(
                os.path.join('/etc/rc.d/init.d', name)
            )
        self.logger.debug(
            'service %s exists %s upstart=%s',
            name,
            ret,
            upstart
        )
        return ret

    def status(self, name):
        self.logger.debug('check service %s status', name)
        (upstart, status) = self._isUpstart(name)
        if not upstart:
            (rc, stdout, stderr) = self._executeServiceCommand(
                name,
                'status',
                raiseOnError=False
            )
            status = rc == 0
        self.logger.debug('service %s status %s', name, status)
        return status

    def startup(self, name, state):
        self.logger.debug('set service %s startup to %s', name, state)
        (upstart, status) = self._isUpstart(name)
        if upstart:
            #
            # upstart does not have the nature of
            # startup configuration?
            #
            pass
        else:
            rc, stdout, stderr = self.execute(
                (
                    self.command.get('chkconfig'),
                    name,
                    'on' if state else 'off',
                ),
                raiseOnError=False,
            )
            if rc != 0:
                raise RuntimeError(
                    _(
                        "Failed to set boot startup {state} "
                        "for service '{service}'"
                    ).format(
                        do=_('on') if state else _('off'),
                        service=name,
                    )
                )

    def state(self, name, state):
        self.logger.debug(
            '%s service %s',
            'starting' if state else 'stopping',
            name
        )
        (upstart, status) = self._isUpstart(name)
        if upstart:
            #
            # upstart fails when multiple
            # start/stop commands.
            #
            if state == status:
                rc = 0
            else:
                rc, stdout, stderr = self._executeInitctlCommand(
                    name,
                    'start' if state else 'stop',
                    raiseOnError=False,
                )
        else:
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
