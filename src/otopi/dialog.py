#
# otopi -- plugable installer
#


"""Dialog interface.

Dialog is the component responsible of intraction with manager.

"""


import getpass
import gettext
import logging
import os
import sys


from . import common
from . import constants
from . import util


def _(m):
    return gettext.dgettext(message=m, domain='otopi')


@util.export
class DialogBase(object):
    """Base class for dialog.

    Base class for all dialog providers.

    """
    def note(self, text, prompt=False):
        """Print human readable note.

        Keyword arguments:
        text -- text to print, may be either list of lines or string.
        prompt -- do not echo new line after note if possible.

        Human readbale note is ignored by manager.

        """
        pass

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
        """Query string from manager.

        Keyword arguments:
        name -- name of variable.
        note -- note to present.
        validValues -- tuple of valid values.
        caseSensitive -- consider validValues as such.
        hidden -- if tty echo will be disabled.
        prompt -- do not echo new line after note if possible.
        default -- if not None use this if empty.

        """
        raise NotImplementedError(_('Dialog queryString not implemented'))

    def queryMultiString(self, name, note=None):
        """Query multi-string from manager.

        Keyword arguments:
        name -- name of variable.
        note -- note to present.

        """
        raise NotImplementedError(_('Dialog queryMultiString not implemented'))

    def queryValue(self, name, note=None):
        """Query value from manager.

        Keyword arguments:
        name -- name of variable.
        note -- note to present.

        """
        raise NotImplementedError(_('Dialog queryValue not implemented'))

    def displayValue(self, name, value, note=None):
        """Display a value to the manager.

        Keyword arguments:
        name -- name of variable.
        value -- value to variable.
        note -- note to present.

        """
        pass

    def displayMultiString(self, name, value, note=None):
        """Display a multi-string to the manager.

        Keyword arguments:
        name -- name of variable.
        value -- value to variable.
        note -- note to present.

        """
        pass

    def confirm(
        self,
        name,
        description,
        note=None,
        prompt=False,
    ):
        """Ask confirmation from manager.

        Keyword arguments:
        name -- name of variable.
        description -- description of request.
        note -- note to present.
        prompt -- do not echo new line after note if possible.

        Returns:
        True -- confirmed.

        """
        return False

    def terminate(self):
        """Notify manager of end of dialog."""
        pass


@util.export
class DialogBaseImpl(DialogBase):

    def __init__(self):
        self.__input = None
        self.__output = None
        self.__handler = None

    def __setupStdHandles(self):
        self.__flush(sys.stdout)
        self.__flush(sys.stderr)
        self.__stdhandles = (
            os.dup(0),
            os.dup(1),
            os.dup(2)
        )
        null = os.open(os.devnull, os.O_RDONLY)
        os.dup2(null, 0)
        os.close(null)
        for i in range(1, 3):
            os.dup2(
                self.environment[constants.CoreEnv.LOG_FILE_HANDLE].fileno(),
                i
            )

    def __setupDialogChannel(self, logFormatter=None):
        self.__input = os.fdopen(
            os.dup(self.__stdhandles[0]),
            'rt',
            1
        )
        self.__output = os.fdopen(
            os.dup(self.__stdhandles[1]),
            'wt',
            1
        )
        self.__handler = logging.StreamHandler(self.__output)
        self.__handler.setLevel(logging.INFO)
        if logFormatter is not None:
            self.__handler.setFormatter(logFormatter)
        l = logging.getLogger(name=constants.Log.LOGGER_BASE)
        l.addHandler(self.__handler)

    def __restoreStdHandles(self):
        self.__flush(sys.stdout)
        self.__flush(sys.stderr)
        if self.__handler is not None:
            l = logging.getLogger(name=constants.Log.LOGGER_BASE)
            l.removeHandler(self.__handler)
            self.__handler.close()
            self.__handler = None
        for i in range(3):
            os.dup2(self.__stdhandles[i], i)

    def __flush(self, stream):
        stream.flush()
        try:
            # tty [at least] gets errors
            os.fsync(stream.fileno())
        except OSError:
            pass

    def __logString(self, name, string):
        for line in string.splitlines():
            self.logger.debug('DIALOG:%-10s %s', name, line)

    def __notification(self, event):
        if event == self.context.NOTIFY_REEXEC:
            self._close()

    def _open(self, logFormatter=None):
        self.__setupStdHandles()
        self.__setupDialogChannel(logFormatter)
        self.context.registerNotification(self.__notification)

    def _close(self):
        if self.__input is not None:
            self.__input.close()
            self.__input = None
        if self.__output is not None:
            self.__output.close()
            self.__output = None
        self.__restoreStdHandles()

    def _output_isatty(self):
        return self.__output.isatty()

    def _readline(self, hidden=False):
        getpass_error = True
        if hidden and self.__input.isatty():
            old = os.dup(0)
            os.dup2(self.__stdhandles[0], 0)
            try:
                with open(os.devnull, 'w+') as null:
                    value = getpass.getpass(prompt='', stream=null)
                    self.__output.write('\n')
                    getpass_error = False
            except RuntimeError as e:
                # probably signal
                raise e
            except:
                self.logger.debug('getpass', exc_info=True)
            finally:
                os.dup2(old, 0)

        if not hidden or getpass_error:
            value = self.__input.readline()
            if not value:
                raise IOError(_('End of file'))

        value = value.rstrip('\n')
        if not hidden:
            self.__logString('RECEIVE', value)
        return value

    def _flush(self):
        self.__flush(stream=self.__output)

    def _write(self, text, flush=True):
        text = common.toStr(text)
        self.__logString('SEND', text)
        self.__output.write(text)
        if flush:
            self.__flush(self.__output)

    def _queryStringNote(
        self,
        name,
        note=None,
        validValues=None,
        default=None,
    ):
        def _subst(s):
            ret = s
            if validValues is not None:
                ret = ret.replace('@VALUES@', ', '.join(validValues))
            if default is not None:
                ret = ret.replace('@DEFAULT@', default)
            return ret

        if note is None:
            note = _("\nPlease specify '{name}'")
            if validValues is not None:
                note += ' (@VALUES@)'
            if default is not None:
                note += ' [@DEFAULT@]'

        if isinstance(note, str):
            note = [note]
        note = [_subst(n) for n in note]

        if len(note) == 1:
            note = note[0]

        return note


# vim: expandtab tabstop=4 shiftwidth=4
