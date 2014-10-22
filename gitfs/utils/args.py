# Copyright 2014 PressLabs SRL
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import getpass
import os
import socket
import tempfile
import grp
import sys
from logging import Formatter
from logging.handlers import TimedRotatingFileHandler, SysLogHandler
from collections import OrderedDict
from urlparse import urlparse

from gitfs.log import log
from gitfs.cache import lru_cache


class Args(object):
    def __init__(self, parser):
        self.DEFAULTS = OrderedDict([
            ("repo_path", (self.get_repo_path, "string")),
            ("user", (self.get_current_user, "string")),
            ("group", (self.get_current_group, "string")),
            ("username", ("", "string")),
            ("password", ("", "string")),
            ("ssh_key", (self.get_ssh_key, "string")),
            ("ssh_user", (self.get_ssh_user, "string")),
            ("foreground", (False, "bool")),
            ("branch", ("master", "string")),
            ("allow_other", (False, "bool")),
            ("allow_root", (True, "bool")),
            ("commiter_name", (self.get_current_user, "string")),
            ("commiter_email", (self.get_current_email, "string")),
            ("max_size", (10, "float")),
            ("fetch_timeout", (30, "float")),
            ("merge_timeout", (5, "float")),
            ("debug", (False, "bool")),
            ("log", ("syslog", "string")),
            ("log_level", ("warning", "string")),
            ("cache_size", (800, "int")),
        ])
        self.config = self.build_config(parser.parse_args())

    def build_config(self, args):
        if args.o:
            for arg in args.o.split(","):
                if "=" in arg:
                    item, value = arg.split("=")
                    setattr(args, item, value)

        return self.check_args(self.set_defaults(args))

    def check_args(self, args):
        # check allow_other and allow_root
        if args.allow_other:
            args.allow_root = False
        else:
            args.allow_root = True

        # check log_level
        if args.debug:
            args.log_level = 'debug'

        # setup logging
        if args.log != "syslog":
            handler = TimedRotatingFileHandler(args.log, when="midnight")
            handler.setFormatter(Formatter(fmt='%(asctime)s %(threadName)s: '
                                           '%(message)s',
                                           datefmt='%B-%d-%Y %H:%M:%S'))
        else:
            if sys.platform == 'darwin':
                handler = SysLogHandler(address="/var/run/syslog")
            else:
                handler = SysLogHandler(address="/dev/log")

            handler.setFormatter(Formatter(fmt='GitFS: %(threadName)s: '
                                           '%(message)s'))

        log.addHandler(handler)
        log.setLevel(args.log_level.upper())

        # set cache size
        lru_cache.maxsize = args.cache_size

        return args

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            return getattr(self.__dict__['config'], attr)

    def set_defaults(self, args):
        for option, value in self.DEFAULTS.iteritems():
            new_value = getattr(args, option, None)

            if not new_value:
                value = value[0]

                if callable(value):
                    value = value(args)
            else:
                if value[1] == "string":
                    value = new_value
                elif value[1] == "bool":
                    if new_value.lower() == "true":
                        value = True
                    if new_value.lower() == "false":
                        value = False
                elif value[1] == "float":
                    value = float(new_value)
                elif value[1] == "int":
                    value = int(new_value)

            setattr(args, option, value)
        return args

    def get_current_group(self, args):
        gid = os.getegid()
        return grp.getgrgid(gid).gr_name

    def get_current_user(self, args):
        return getpass.getuser()

    def get_current_email(self, args):
        return "%s@%s" % (args.user, socket.gethostname())

    def get_repo_path(self, args):
        return tempfile.mkdtemp(dir="/var/lib/gitfs")

    def get_ssh_key(self, args):
        return os.environ["HOME"] + "/.ssh/id_rsa"

    def get_ssh_user(self, args):
        url = args.remote_url
        parse_result = urlparse(url)
        if not parse_result.scheme:
            url = 'ssh://' + url
            parse_result = urlparse(url)
        return parse_result.username if parse_result.username else ""
