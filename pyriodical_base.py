"""Periodically perform some action.

author
    Written by Mica Eldridge, 2016-01-31U
notes
    writes to performed file '{performed_file}',
    which is relative to this script.
side-effects
    upon success, writes token to "performed file"
version 0.1
2016-01-16S

To define a functioning periodical subclass, read the documentation
for these methods and override them:
    required:
        make_unique_token
        perform
    optional:
        should_perform_now
        recover_from_error
"""
import os
import argparse
import sys
import logging
import subprocess
import traceback
import datetime

from class_schedule import in_class

from .platforms import PlatformFactory


class PyriodicalBase:

    def __init__(self, filename_part, confirm_user_str=None):
        """Declare the base behavior for a Periodical

        :param filename_part: str a short, unique string that will be
            used to create the "performed file" and keep track of
            completed perform tokens
        :param confirm_user_str: str to display to the user to ask for
            confirmation before performing the action. default None,
            don't ask user for confirmation before performing the
            action.
        """
        self.platform = PlatformFactory.get_platform()
        self.filename_part = filename_part
        self.confirm_user_str = confirm_user_str
        self.logger = None
        self.performed_file = self._get_performed_file_name()
        self.description = '{}\n{}'.format(
            self.__doc__ or '',
            __doc__.format(
                performed_file=self.performed_file
            ),
        )
        self.name = type(self).__name__
        self.arg_parser = self.get_arg_parser()

    def get_arg_parser(self):

        arg_parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawTextHelpFormatter
        )

        arg_parser.add_argument(
            '-s', '--status',
            default=False, action='store_true',
            help="get status of this periodical, and exit"
        )

        arg_parser.add_argument(
            '-c', '--could-run-now',
            default=False, action='store_true',
            help="print whether this pyriodical could run now, "
                 "and exit"
        )

        arg_parser.add_argument(
            '-f', '--force',
            default=False, action='store_true',
            help="run even if the token has already been run"
        )

        if self.platform.supports('open_text_file'):
            arg_parser.add_argument(
                '-e', '--edit-perform-file',
                default=False, action='store_true',
                help="open the performed file in the application your"
                     " platform supports, and exit"
            )

        return arg_parser

    def should_perform_now(self):
        """Determine whether this script should run now

        Not every script should run all the time. Return False if you
        don't want to perform this script. A good example is that some
        scripts only make sense on the weekend, and others only on
        weekdays.

        If ever a script should be skipped, the script should override
        this method with the appropriate logic. The default is to
        always perform.

        The default is to always perform.

        :rtype: bool True if it should perform now, otherwise False
        """
        return True

    def perform(self):
        """Perform the action that this periodical represents

        :rtype: bool True on success, False on failure
        """
        raise NotImplementedError("perform must be "
                                  "overridden in subclass")

    def recover_from_error(self, exception):
        """Do something if the script doesn't execute successfully

        By default, ignore failures. Override in subclasses for
        alternate behavior.

        Two potential recoveries may be logging the exception or
        generating a warning popup.

        :param exception: Exception that was thrown so that
            recover_from_error can choose to handle it in some way.
        """
        pass

    @staticmethod
    def can_reach_server(server):
        # TODO some servers don't accept ping. should handle those cases.
        command = '/sbin/ping -c 1 {server} -t 1 >>/dev/null 2>&1'.format(server=server)
        return subprocess.call(command, shell=True) == 0

    _has_internet = None
    _last_internet_check_dt = None

    @classmethod
    def has_internet(cls):
        # haven't checked yet, so immediately check and return
        if cls._last_internet_check_dt is None:
            cls._last_internet_check_dt = datetime.datetime.now()
            cls._has_internet = (
                cls.can_reach_server('8.8.8.8')
                or cls.can_reach_server('8.8.4.4')
            )
            return cls._has_internet

        last_checked_internet_minutes = (datetime.datetime.now() - cls._last_internet_check_dt).total_seconds() / 60
        if cls._has_internet and last_checked_internet_minutes < 1:
            return cls._has_internet

        cls._has_internet = (
            cls.can_reach_server('8.8.8.8')
            or cls.can_reach_server('8.8.4.4')
        )
        cls._last_internet_check_dt = datetime.datetime.now()

        return cls._has_internet

    def _edit_perform_file(self):
        """Edit the "performed" file

        For this to work, a subclass must override open_text_file with
        a platform-specific implementation.
        """
        pass

    def _ensure_performed_file(self):
        """Ensure that the performed file exists
        """
        if not os.path.exists(self.performed_file):
            with open(self.performed_file, 'a') as fw:
                print('', end='', file=fw)

    def _have_performed(self, token):
        """Check if have performed for the current token

        :param token: str token for this run
        :rtype: bool True if already performed for this token,
            otherwise False
        """
        return self._get_last_performed() == token

    def _ensure_performed_file_dir(self):
        """Ensure the directory for the performed file exists

        Create the directory for the performed file if it doesn't
        already exist.
        """
        performed_file_dir = os.path.dirname(self.performed_file)
        if not os.path.exists(performed_file_dir):
            os.makedirs(performed_file_dir)

    def _mark_performed(self, token):
        """Record that we have performed the task

        Writes token to the "performed file". Rather than generating
        token on the spot, token is a parameter, because the token
        at time of completion may be different than the token at the
        time the script started, and we don't want a script that
        started some time ago to override any future run.

        :param token: str token for this run
        """
        with open(self.performed_file, 'a') as fw:
            print(token, file=fw)

    def make_unique_token(self):
        """Make a unique token that represents one run of this script

        Control how often a run occurs. Instead of controlling how
        often a script runs by putting specific time rules in crontab
        (which may fail or be dismissed by the user), run the script
        once per hour and let the script decide if it should run or
        not. In cron-speak, once per hour is "0 * * * *".

        A "period" is the range of time for which a token spans. If a
        script is meant to be run once per day, then the token is most
        likely the day's date, e.g. "2016-01-31", and the period is
        "a day".

        For scripts that ask the user for confirmation before
        running, this allows the user to dismiss a run and let it
        attempt to run on the same token at the next hour mark. For
        scripts that may fail, the same is true.

        A run will only occur once per token ("period"). If one token
        spans multiple hour marks, then it will only run once
        (successfully) during those hour marks.

        Example: you want to automatically reduce the volume on your
        computer once per day. The token should be the day's date,
        e.g. str(datetime.datetime.today()), which returns
        "2016-01-31". When this script runs for a second time on the
        same day, the script will see that the token already appears
        in the "performed file", and not perform the action again.
        If you want to perform once per hour, include the hour in the
        token (e.g. "2016-01-31 13"). If you want to perform twice per
        day, once before 5pm and once at or after 5pm, then
        if datetime.datetime.now().hour >= 17:
            token += '-1'
        else:
            token += '-2'
        Will perform two different tokens during those two periods:
        "2016-01-31-1" and "2016-01-31-2". The addition could just as
        easily be "before 5pm" and "at or after 5pm".

        The token of a given run should be generated at the beginning
        of the run and be reused until completion (i.e. used for
        marking that it has performed). This is so that if a
        particular script takes a long time to run, late completion of
        one run doesn't prevent the following run from performing.
        """
        raise NotImplementedError("make_unique_token must be "
                                  "overridden in subclass")

    def get_logger(self):
        """Get a logger, lazy-initialization style.

        The logger will be named after the subclass so that the log
        messages will make more sense.

        :rtype: logging.Logger corresponding to the subclass
        """

        if self.logger is None:

            logging.basicConfig(level=logging.DEBUG)
            # set level of root logger
            logging.getLogger().setLevel(logging.DEBUG)

            self.logger = logging.getLogger(self.name)
            self.logger.setLevel(level=logging.DEBUG)

        return self.logger

    def _get_performed_file_name(self):
        """Get the name of the performed file

        :rtype: str absolute path to the name of the performed file
        """
        executable = sys.argv[0]
        dirname = os.path.dirname(executable)

        filename = os.path.join(
            dirname,
            'data',
            'performed',
            self.filename_part + '.txt',
        )

        return filename

    def _get_last_performed(self):
        """Get the most recent token that was performed successfully

        :rtype: str token corresponding to the most recent run
        """
        last_perform = None
        with open(self.performed_file, 'r') as fr:
            try:
                last_perform = next(fr)
            except StopIteration:
                return None
            for last_perform in fr:
                pass

        if last_perform is not None:
            last_perform = last_perform.strip()

        return last_perform

    def did_perform_token(self, token):
        """Check if the given token was performed

        :param token: str token to check for
        :rtype: bool True if this token was performed, otherwise False
        """
        performed = False
        with open(self.performed_file, 'r') as fr:
            for line in fr:
                if line.strip() == token:
                    performed = True
                    break

        return performed

    def could_run_now(self, token):
        """Check if running this periodical would start a run

        :param token: str token for the run to check
        :rtype: bool True if it could perform now, otherwise False
        """
        perfd_this_token = self.did_perform_token(token)
        should_perform = self.should_perform_now()
        return should_perform and not perfd_this_token

    def _get_status(self, token):
        """Get the status of this periodical

        Not completely implemented. This cannot be completely
        implemented until PID file issue is completed, so that we can
        tell if the periodical is running right now.

        Possible statuses:
            running, token
                True if a run is in progress, and the token that the
                current run is using
            last performed token
                the token of the most recent successfully completed
                run
            should perform now
                True if running right now would cause this periodical
                to begin a run
            current token
                token that would be valid if the run started now
            performed for this token
                True if the current token has already been performed

        This is not necessarily an exhaustive list of all the possible
        statuses.

        The status should include a human-readable description of
        where the periodical currently stands.

        :param token: str token that would be valid for a current run
        :rtype: str describing the status
        """
        last_token = self._get_last_performed()
        perfd_this_token = self.did_perform_token(token)
        should_perform = self.should_perform_now()
        cld_run_now = self.could_run_now(token)
        return (
            "periodical name:          {periodical_name}\n"
            "could run now:            {cld_run_now}\n"
            "performed for this token: {perfd_this_token}\n"
            "last performed token:     {last_token}\n"
            "current token:            {token}\n"
            "should perform now:       {should_perform}\n"
        ).format(
            periodical_name=self.name,
            last_token=last_token,
            should_perform=should_perform,
            token=token,
            perfd_this_token=perfd_this_token,
            cld_run_now=cld_run_now,
        )

    def needs_internet(self):
        return False

    def main(self, log=False):
        """Run the periodical
        """
        cl_args = self.arg_parser.parse_args()

        # create performed directory and file if they don't exist
        self._ensure_performed_file_dir()
        self._ensure_performed_file()

        if getattr(cl_args, 'edit_perform_file', False):
            self.platform.open_text_file(self.performed_file)
            return

        token = self.make_unique_token()
        if getattr(cl_args, 'status', False):
            print(self._get_status(token))
            return
        if getattr(cl_args, 'could_run_now', False):
            print('could run now: {} {}'.format(
                self.could_run_now(token), self.name
            ))
            return

        # shouldn't perform now, or already performed
        if not self.should_perform_now():
            return
        if self._have_performed(token) and not cl_args.force:
            return

        # if this periodical requires confirmation before executing,
        # the platform supports asking confirmation, and user doesn't
        # want to run it, then don't run it
        if (self.confirm_user_str is not None and
                self.platform.supports('confirm_user') and
                not self.platform.confirm_user(self.confirm_user_str)):
            return

        needs_internet = self.needs_internet()
        has_internet = self.has_internet() if needs_internet else None

        if needs_internet and not has_internet:
            if log:
                self.get_logger().error(
                    "need internet but has no internet; can't perform; exiting"
                )
            return 1

        if log:
            self.get_logger().info("performing {}".format(self.name))

        try:
            success = self.perform()
        except KeyboardInterrupt:
            raise
        except Exception as exception:
            print(traceback.format_exc())
            self.recover_from_error(exception)
            raise

        if success:
            self._mark_performed(token)

        exit_code = 0 if success else 1
        return exit_code

    @staticmethod
    def in_class():
        return in_class()
