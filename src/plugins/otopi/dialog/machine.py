#
# otopi -- plugable installer
#


"""Machine dialog provider

Refer to README.dialog.

"""


import gettext
import logging


from otopi import common
from otopi import constants
from otopi import context
from otopi import dialog
from otopi import plugin
from otopi import util


from . import constants as dialogcons


def _(m):
    return gettext.dgettext(message=m, domain='otopi')


@util.export
class Plugin(plugin.PluginBase, dialog.DialogBaseImpl):
    """Machine dialog protocol provider.

    Environment:
        DialogEnv.DIALECT -- if machine activate.
        DialogEnv.BOUNDARY -- set bundary to use.

    """
    BOUNDARY = '--=451b80dc-996f-432e-9e4f-2b29ef6d1141=--'
    ABORT_BOUNDARY = '--=451b80dc-996f-ABORT-9e4f-2b29ef6d1141=--'

    class _MyFormatter(logging.Formatter):
        """No new-line formatter."""
        def __init__(self, parent):
            logging.Formatter.__init__(
                self,
                fmt=(
                    dialogcons.DialogMachineConst.REQUEST_PREFIX +
                    dialogcons.DialogMachineConst.LOG_PREFIX +
                    '%(levelname)s %(message)s'
                ),
            )
            self._parent = parent

        def format(self, record):
            return logging.Formatter.format(self, record).replace('\n', ' ')

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        dialog.DialogBaseImpl.__init__(self)    # python super is no good
        self._enabled = False

    @plugin.event(
        stage=plugin.Stages.STAGE_BOOT,
        priority=plugin.Stages.PRIORITY_MEDIUM,
        condition=(
            lambda self: self.environment[
                constants.DialogEnv.DIALECT
            ] == constants.Const.DIALOG_DIALECT_MACHINE
        ),
    )
    def _init(self):
        self.environment[constants.DialogEnv.BOUNDARY] = self.BOUNDARY
        self._open(logFormatter=self._MyFormatter(parent=self))
        self._enabled = True
        self.context.registerDialog(self)

    @plugin.event(
        stage=plugin.Stages.STAGE_TERMINATE,
        priority=plugin.Stages.PRIORITY_LAST + 10,
        condition=lambda self: self._enabled,
    )
    def _terminate(self):
        self.dialog.terminate()
        self._close()

    #
    # DialogBase
    #

    def note(self, text=None, prompt=False):

        PREFIX = '{p}{p}{p}'.format(
            p=dialogcons.DialogMachineConst.NOTE_PREFIX
        )

        if isinstance(text, list) or isinstance(text, tuple):
            for i in text:
                self.note(text=i)
            return

        if text is None:
            text = '\n'
        text = common.toStr(text)

        for line in text.splitlines():
            self._write(
                text='%s%s\n' % (
                    PREFIX,
                    ' ' + line if line else ''
                ),
                flush=False,
            )
        self._flush()

    def _writeQueryStart(self, name):
        self._write(
            text='%s%s %s\n' % (
                dialogcons.DialogMachineConst.QUERY_EXTRA_PREFIX,
                dialogcons.DialogMachineConst.QUERY_START,
                name,
            )
        )

    def _writeQueryEnd(self, name):
        self._write(
            text='%s%s %s\n' % (
                dialogcons.DialogMachineConst.QUERY_EXTRA_PREFIX,
                dialogcons.DialogMachineConst.QUERY_END,
                name,
            )
        )

    def queryString(
        self,
        name,
        note=None,
        validValues=None,
        caseSensitive=True,
        hidden=False,
        prompt=False,
        default=None,
    ):
        if default is not None:
            default = common.toStr(default)
        if validValues is not None:
            validValues = [common.toStr(v) for v in validValues]
        note = self._queryStringNote(
            name=name,
            note=note,
            validValues=validValues,
            default=default,
        )

        self._writeQueryStart(name)
        self.dialog.note(text=note, prompt=prompt)
        if default:
            self._write(
                text='%s%s %s\n' % (
                    dialogcons.DialogMachineConst.QUERY_EXTRA_PREFIX,
                    dialogcons.DialogMachineConst.QUERY_DEFAULT_VALUE,
                    default,
                )
            )
        if validValues:
            self._write(
                text='%s%s %s\n' % (
                    dialogcons.DialogMachineConst.REQUEST_PREFIX,
                    dialogcons.DialogMachineConst.QUERY_VALID_VALUES,
                    '|'.join(
                        [
                            x.replace('\\', '\\\\').replace('|', '\|')
                            for x in validValues
                        ]
                    ),
                )
            )
        self._write(
            text='%s%s %s\n' % (
                dialogcons.DialogMachineConst.QUERY_EXTRA_PREFIX,
                dialogcons.DialogMachineConst.QUERY_HIDDEN,
                (
                    dialogcons.DialogMachineConst.QUERY_HIDDEN_TRUE if hidden
                    else dialogcons.DialogMachineConst.QUERY_HIDDEN_FALSE
                )
            )
        )

        self._write(
            text='%s%s %s\n' % (
                dialogcons.DialogMachineConst.REQUEST_PREFIX,
                dialogcons.DialogMachineConst.QUERY_STRING,
                name,
            )
        )
        self._writeQueryEnd(name)
        if not caseSensitive and validValues is not None:
            validValues = [v.lower() for v in validValues]
        value = self._readline(hidden)
        if not value and default is not None:
            value = default
        if not caseSensitive:
            value = value.lower()
        if (
            (validValues is not None and value not in validValues) or
            (not value and value != default)
        ):
            raise RuntimeError(
                _("Invalid value provided to '{name}'").format(
                    name=name
                )
            )
        return value

    def queryMultiString(self, name, note=None):
        if note is None:
            note = _("\nPlease specify multiple strings for '{name}':").format(
                name=name
            )
        self._writeQueryStart(name)
        self.dialog.note(text=note)
        self.dialog.note(
            text=_(
                "type '{boundary}' in own line to mark end, "
                "'{abortboundary}' aborts"
            ).format(
                boundary=self.BOUNDARY,
                abortboundary=self.ABORT_BOUNDARY,
            )
        )
        self._write(
            text='%s%s %s %s %s\n' % (
                dialogcons.DialogMachineConst.REQUEST_PREFIX,
                dialogcons.DialogMachineConst.QUERY_MULTI_STRING,
                name,
                self.BOUNDARY,
                self.ABORT_BOUNDARY,
            )
        )
        self._writeQueryEnd(name)
        value = []
        while True:
            v = self._readline()
            if v == self.BOUNDARY:
                break
            elif v == self.ABORT_BOUNDARY:
                raise context.Abort(_('Aborted by dialog'))
            value.append(v)

        return value

    def queryValue(self, name, note=None):
        if note is None:
            note = _("\nPlease specify value for '{name}':").format(
                name=name
            )

        self._writeQueryStart(name)
        self.dialog.note(text=note)
        self.dialog.note(
            text=_(
                "Response is VALUE {name}=type:value or "
                "ABORT {name}"
            ).format(
                name=name,
            ),
        )
        self._write(
            text='%s%s %s\n' % (
                dialogcons.DialogMachineConst.REQUEST_PREFIX,
                dialogcons.DialogMachineConst.QUERY_VALUE,
                name,
            )
        )
        self._writeQueryEnd(name)

        opcode, variable = self._readline().split(' ', 1)
        variable = variable.split('=', 1)

        if variable[0] != name:
            raise RuntimeError(
                _(
                    "Expected response for {name}, "
                    "received '{received}'"
                ).format(
                    name=name,
                    received=variable[0],
                )
            )

        if opcode == dialogcons.DialogMachineConst.QUERY_VALUE_RESPONSE_ABORT:
            raise context.Abort(_('Aborted by dialog'))
        elif opcode == \
                dialogcons.DialogMachineConst.QUERY_VALUE_RESPONSE_VALUE:
            if len(variable) != 2:
                raise RuntimeError(_('Value ot provided'))
            return common.parseTypedValue(variable[1])
        else:
            raise RuntimeError(
                _("Invalid response opcode '{code}'").format(
                    code=opcode,
                )
            )

    def displayValue(self, name, value, note=None):
        if note is not None:
            self.note(text=note)

        self._write(
            text='%s%s %s=%s:%s\n' % (
                dialogcons.DialogMachineConst.REQUEST_PREFIX,
                dialogcons.DialogMachineConst.DISPLAY_VALUE,
                name,
                common.typeName(value),
                value,
            )
        )

    def displayMultiString(self, name, value, note=None):
        if note is not None:
            self.note(text=note)

        self._write(
            text='%s%s %s %s\n%s%s%s\n' % (
                dialogcons.DialogMachineConst.REQUEST_PREFIX,
                dialogcons.DialogMachineConst.DISPLAY_MULTI_STRING,
                name,
                self.BOUNDARY,
                '\n'.join(value),
                '\n' if value else '',
                self.BOUNDARY,
            )
        )

    def confirm(
        self,
        name,
        description,
        note=None,
        prompt=False,
    ):
        if note is None:
            note = _(
                "\nPlease confirm '{name}' {description}\n"
            ).format(
                name=name,
                description=description,
            )
        self._write(
            text='%s%s %s %s\n' % (
                dialogcons.DialogMachineConst.REQUEST_PREFIX,
                dialogcons.DialogMachineConst.CONFIRM,
                name,
                description
            )
        )
        self.dialog.note(
            text=note,
            prompt=prompt,
        )
        self.dialog.note(
            text=_(
                "Response is CONFIRM {name}=yes|no or "
                "ABORT {name}"
            ).format(
                name=name,
            ),
        )

        opcode, variable = self._readline().split(' ', 1)
        variable = variable.split('=', 1)

        if variable[0] != name:
            raise RuntimeError(
                _(
                    "Expected response for {name}, "
                    "received '{received}'"
                ).format(
                    name=name,
                    received=variable[0],
                )
            )

        if opcode == dialogcons.DialogMachineConst.CONFIRM_RESPONSE_ABORT:
            raise context.Abort(_('Aborted by dialog'))
        elif opcode == \
                dialogcons.DialogMachineConst.CONFIRM_RESPONSE_VALUE:
            if len(variable) != 2:
                raise RuntimeError(_('Value ot provided'))
            return variable[1] in ('yes', 'YES', 'y', 'Y')
        else:
            raise RuntimeError(
                _("Invalid response opcode '{code}'").format(
                    code=opcode,
                )
            )

    def terminate(self):
        self._write(
            text='%s%s\n' % (
                dialogcons.DialogMachineConst.REQUEST_PREFIX,
                dialogcons.DialogMachineConst.TERMINATE,
            )
        )


# vim: expandtab tabstop=4 shiftwidth=4
