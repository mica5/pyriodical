"""Choose the right platform

author
    Written by Mica Eldridge, 2016-01-31U
version 0.1
2016-01-31U
"""
import sys
import subprocess


class Platform:

    def __init__(self, supported=tuple()):
        """Initialize a Platform

        :param supported: tuple[str]
        """
        self.supported = supported

    def supports(self, method):
        """Check whether a method is supported

        :param method: str name of method to check
        """
        return method in self.supported

    def confirm_user(self, message):
        """Platform-specific way to ask a user for permission to run

        For scripts that you wish to ask a user for permission to run,
        this method must be overridden in a platform-specific
        subclass.

        This should create a popup that tells the user which script is
        being run, and ask whether they want to run it, with the
        ability of the user to accept or decline. An example in mac is
        osascript/applescript's "display dialog".

        :param message: str to display to the user
        :rtype: bool True if user wants to run, otherwise False
        """
        raise NotImplementedError("confirm_user must be overridden "
                                  "in subclass")

    def open_text_file(self, file_path):
        """Platform-specific way to open a text file

        Override in platform-specific subclass.
        :param file_path: str path to file to open
        """
        raise NotImplementedError("open_text_file must be "
                                  "overridden in subclass")


class MacPlatform(Platform):
    """Mac-specific support for additional periodical functionality
    """

    supported = (
        'confirm_user',
        'open_path',
        'open_text_file',
    )

    def __init__(self):
        super().__init__(
            supported=self.supported,
        )

    def wait_user(self, message, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL, timeout=3600, **kwargs):
        """Wait for user input.

        :param message: str to display to the user
        :param stdout: int constant from subprocess to direct stdout,
            default subprocess.DEVNULL
        :param stderr: int constant from subprocess to direct stderr,
            default subprocess.DEVNULL
        :param timeout: int in seconds, default 1 hour
        :param kwargs: dict remaining keyword arguments that will be
            passed to subprocess.call
        """
        command = ["""osascript <<EOF
            tell application "System Events"
                with timeout of 86400 seconds
                    display dialog "{message}"
                end timeout
            end tell\nEOF""".format(
            #timeout=timeout,
            message=message
        )]
        exit_code = subprocess.call(
            command,
            stdout=stdout,
            stderr=stderr,
            shell=True,
            **kwargs
        )
        return exit_code

    def confirm_user(self, message):
        """Get permission from the user

        :param message: str to display to the user
        """
        user_choice = self.wait_user(message)
        proceed = user_choice == 0
        return proceed

    def open_path(self, application, path):
        """Open a given path in a given application

        :param application: str to use to open the path
        :param path: str path to open
        """
        subprocess.call(
            'open -a'.split() + [
                application, path
            ]
        )

    def open_text_file(self, file_path):
        """Open a text file on a mac using TextEdit

        Because every mac has TextEdit, we'll use that.
        You can override this by making subclassing this class and
        overriding this method.

        :param file_path: str of text file to open
        """
        self.open_path('TextEdit', file_path)


class LinuxPlatform(Platform):

    supported = tuple()

    def __init__(self):
        super().__init__(
            supported=self.supported,
        )


class WindowsPlatform(Platform):

    supported = tuple()

    def __init__(self):
        super().__init__(
            supported=self.supported,
        )


class PlatformFactory:

    @staticmethod
    def get_platform():
        """Get additional functionality for the underlying platform

        Uses sys.platform.

        :rtype: Platform object corresponding to the host computer
            running this program
        """

        # determine platform
        platform = sys.platform.lower()

        if 'darwin' in platform:
            return MacPlatform()

        elif 'linux' in platform:
            return LinuxPlatform()

        elif platform.startswith('win'):
            return WindowsPlatform()

        else:
            return Platform()
