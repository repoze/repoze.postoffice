from __future__ import with_statement

from cStringIO import StringIO
from ConfigParser import ConfigParser
from contextlib import contextmanager
import datetime
from email.utils import parsedate
import logging
from mailbox import Maildir
from mailbox import MaildirMessage
from mailbox import NoSuchMailboxError
import os
import re
import shutil
import transaction

from repoze.postoffice.filters import ToHostnameFilter
from repoze.postoffice.queue import QueuesFolder
from repoze.postoffice.queue import Queue
from repoze.zodbconn.uri import db_from_uri

MAIN_SECTION = 'post office'
_marker = object()
_discarded = object()

class PostOffice(object):
    """
    Provides server side API for repoze.postoffice.
    """

    # Overridable for testing
    Maildir = Maildir
    MaildirMessage = MaildirMessage
    Queue = Queue

    def __init__(self, filename, db_from_uri=db_from_uri, open=open):
        """
        Initialize from configuration file.
        """
        # db_from_uri and open passed in for unittesting
        here = os.path.dirname(os.path.abspath(filename))
        fp = _load_fp(open(filename))
        self._section_indices = _get_section_indices(fp)
        fp.seek(0)
        config = ConfigParser(defaults=dict(here=here))
        config.readfp(fp)
        self._init_main_section(config)
        self._get_root = _RootContextManagerFactory(
            self.zodb_uri, db_from_uri, self.zodb_path
        )
        self._init_queues(config)

    def _init_main_section(self, config):
        if not config.has_section(MAIN_SECTION):
            raise ValueError('Config file is missing required section: %s' %
                             MAIN_SECTION)

        self.zodb_uri = _get_opt(config, MAIN_SECTION, 'zodb_uri')
        self.maildir = _get_opt(config, MAIN_SECTION, 'maildir')
        self.zodb_path = _get_opt(config, MAIN_SECTION, 'zodb_path',
                                     '/postoffice')
        self.ooo_loop_frequency = _get_opt_float(
            config, MAIN_SECTION, 'ooo_loop_frequency', '0')
        self.ooo_throttle_period = datetime.timedelta(seconds=_get_opt_int(
            config, MAIN_SECTION, 'ooo_throttle_period', '300'))
        self.max_message_size = _get_opt_bytes(
            config, MAIN_SECTION, 'max_message_size', '0')

    def _init_queues(self, config):
        queues = []
        for section in config.sections():
            if section.startswith('queue:'):
                queues.append(self._init_queue(config, section))

        # ConfigParser doesn't preserve section ordering, but we're interested
        # processing queues in the order they appear in the config file, so
        # we've done our own scan to pick out the sections and their relative
        # indices and use that now to sort the queues.
        section_indices = self._section_indices
        queues.sort(key=lambda q: section_indices[q['section']])
        self.configured_queues = queues

    def _init_queue(self, config, section):
        name = section[6:] # len('queue:') == 6
        filters = []
        for option in config.options(section):
            if option == 'filters':
                for filter_ in [f.strip() for f in
                                config.get(section, option)
                                .strip().split('\n')]:
                    filters.append(self._init_filter(filter_))
            elif option == 'here':
                pass
            else:
                raise ValueError('Unknown config parameter for queue: %s' %
                                 option)

        return dict(name=name, filters=filters, section=section)

    def _init_filter(self, filter_):
        name, config = filter_.split(':')
        if name == 'to_hostname':
            return ToHostnameFilter(config.strip())

        raise ValueError("Unknown filter type: %s" % name)

    def reconcile_queues(self, log=None):
        """
        Reconciles queues found in configuration with queues in database.  If
        new queues have been added to the configuration, those queues are
        added to the database.  If old queues have been removed from the
        configuration, they are removed from the database if they are empty.
        If a queue has been removed from the configuration but still has
        queued messages a warning is logged and queue is not removed.
        """
        # Reconcile configured queues with queues in db
        configured = self.configured_queues
        with self._get_root() as root:
            # Create new queues
            for queue in configured:
                name = queue['name']
                if name not in root:
                    root[name] = self.Queue()
                    if log is not None:
                        log.info('Created new postoffice queue: %s' % name)

            # Remove old queues if empty
            configured_names = set([q['name'] for q in configured])
            for name, queue in root.items():
                if name not in configured_names:
                    if len(queue):
                        if log is not None:
                            log.warn(
                                "Queue removed from configuration still has "
                                "messages: %s" % name
                            )
                    else:
                        if log is not None:
                            log.info('Removed old postoffice queue: %s' % name)
                        del root[name]

    def import_messages(self, log=None):
        """
        Imports messages from an external maildir, matches them to queues and
        either stores or discards each message depending on whether it matches
        a queue definition.  Once a message is imported it is removed from the
        maildir.
        """
        factory = _message_factory_factory(self, self.MaildirMessage, log)
        maildir = self.Maildir(self.maildir, factory=factory, create=True)
        keys = list(maildir.keys())
        keys.sort()
        for key in keys:
            message = maildir.get_message(key)
            if message is _discarded:
                maildir.remove(key)
                continue
            self._import_message(message, log)
            self._archive_message(maildir, message, key)
        if log is not None:
            n = len(keys)
            if n == 1:
                log.info("Processed one message.")
            else:
                log.info("Processed %d messages." % n)

    def _import_message(self, message, log):
        user = message.get('From')
        if user is None:
            if log is not None:
                log.info("Message discarded: no 'From' header: %s" %
                         _log_message(message))
            return

        now = message.get('Date')
        if now is not None:
            now = datetime.datetime(*parsedate(now)[:6])
        else:
            now = datetime.datetime.now()

        for configured in self.configured_queues:
            filters = configured['filters']
            if not filters or not _filters_match(filters, message):
                continue

            # Matches queue
            with self._get_root() as queues:
                name = configured['name']
                queue = queues[name]
                if queue.is_throttled(user, now):
                    queue.collect_frequency_data(message)
                    log.info("Message discarded, user throttled: %s" %
                             _log_message(message))
                    break

                freq = self.ooo_loop_frequency
                if freq:
                    # If instanteous or average frequency exceeds limit,
                    # throttle user. For average frequency, use interval that
                    # is 4 times the inverse of the the freqency. IE, if
                    # frequency is 0.25/minute, then 1/frequency is 4 minutes
                    # and interval to average over is 16 minutes.
                    interval = datetime.timedelta(minutes=4*1/freq)
                    if (queue.get_instantaneous_frequency(user, now) > freq or
                        queue.get_average_frequency(user, now, interval) >
                        freq):
                        queue.throttle(user, now + self.ooo_throttle_period)
                        queue.collect_frequency_data(message)
                        log.info("Message discarded, user triggered "
                                 "throttle: %s" % _log_message(message))
                        break

                queue.add(message)
                queue.collect_frequency_data(message)
                if log is not None:
                    log.info("Message added to queue, %s: %s" %
                             (name, _log_message(message))
                             )
                break

        else:
            if log is not None:
                log.info("Message discarded, no matching queues: %s" %
                         _log_message(message))

    def _archive_message(self, maildir, message, key):
        # XXX It would be nice to wire into transaction with a data manager
        today = datetime.date.today().timetuple()[:3]
        name = '%4d.%02d.%02d' % today
        try:
            folder = maildir.get_folder(name)
        except NoSuchMailboxError:
            folder = maildir.add_folder(name)
        folder.add(message)
        maildir.remove(key)

def _get_opt(config, section, name, default=_marker):
    if config.has_option(section, name):
        return config.get(section, name)
    elif default is not _marker:
        return default
    raise ValueError('Missing required configuration parameter: %s' % name)

def _get_opt_int(config, section, name, default=_marker):
    value = _get_opt(config, section, name, default)
    try:
        return int(value)
    except:
        raise ValueError('Value for %s must be an integer' % name)

def _get_opt_float(config, section, name, default=_marker):
    value = _get_opt(config, section, name, default)
    try:
        return float(value)
    except:
        raise ValueError('Value for %s must be a floating point number' % name)

def _get_opt_bytes(config, section, name, default=_marker):
    value = _get_opt(config, section, name, default).lower()
    num, unit = value, ''
    for i in xrange(len(value)):
        if value[i] < '0' or value[i] > '9':
            num, unit = value[:i], value[i:]
            break
    if not len(num):
        raise ValueError('Value for %s must be an integer' % name)
    value = int(num)
    if not len(unit):
        return value
    elif unit in ('k', 'kb'):
        return value * 1<<10
    elif unit in ('m', 'mb'):
        return value * 1<<20
    elif unit in ('g', 'gb'):
        return value * 1<<30
    else:
        raise ValueError('Bad units in bytes value for %s: %s' % (name, unit))

def _load_fp(fp):
    """
    Read contents of file-like object into memory.
    """
    buf = StringIO()
    shutil.copyfileobj(fp, buf)
    buf.seek(0)
    return buf

def _get_section_indices(fp):
    """
    Get sections in order they appear in a config file.  We do this to
    reconstruct later the order that queues appeared in the config file, since
    ConfigParser does not preserve section ordering.
    """
    indices = {}
    index = 0
    for line in fp:
        if not line.startswith('['):
            continue

        line = line.strip()
        if not line.endswith(']'):
            continue

        indices[line[1:-1]] = index
        index += 1

    return indices

def _filters_match(filters, message):
    for filter_ in filters:
        if not filter_(message):
            return False
    return True

def _log_message(message):
    info = ['Message']
    if 'From' in message:
        info.append('From: %s' % message['From'])
    if 'To' in message:
        info.append('To: %s' % message['To'])
    if 'Subject' in message:
        info.append('Subject: %s' % message['Subject'])
    if 'Message-Id' in message:
        info.append('Message-Id: %s' % message['Message-Id'])
    return ' '.join(info)

class _RootContextManagerFactory(object):
    """
    Gets the root postoffice object, an instance of
    `repoze.postoffice.queue.QueuesFolder`.  If folder does not exist it is
    created.  It's parent, however, must already exist if a nested zodb_path
    is used.
    """
    def __init__(self, uri, db_from_uri, path):
        self.uri = uri
        self.db_from_uri = db_from_uri
        self.path = path.strip('/').split('/')

    @contextmanager
    def __call__(self):
        db = self.db_from_uri(self.uri)
        conn = db.open()
        parent = conn.root()
        for name in self.path[:-1]:
            parent = parent[name]
        name = self.path[-1]
        try:
            folder = parent.get(name)
            if folder is None:
                folder = QueuesFolder()
                parent[name] = folder
            yield folder
        except:
            transaction.abort()
            raise
        else:
            transaction.commit()
        finally:
            conn.close()
            db.close()

import smtplib
def _send_mail(from_addr, to_addrs, message, smtplib=smtplib):
    """
    Sends mail message immediately through SMTP server located on localhost.

    XXX Add some configuration knobs.
    """
    # smtplib passed in for testing
    if not isinstance(message, str):
        message = message.as_string()
    mta = smtplib.SMTP('localhost')
    mta.sendmail(from_addr, to_addrs, message)

def _message_factory_factory(po, wrapped, log):
    def factory(fp):
        headers = _read_message_headers(fp)

        # Check for signs of automated reply

        # Like Mailman, if a message has "Precedence: bulk|junk|list",
        # discard it.  The Precedence header is non-standard, yet
        # widely supported.
        precedence = headers.get('Precedence', '').lower()
        if precedence in ('bulk', 'junk', 'list'):
            if log is not None:
                log.info("Message discarded, automatic reply: %s" %
                         _log_message(headers))
            return _discarded

        # rfc3834 is the standard way to discard automated responses, but
        # it is not yet widely supported.
        auto_submitted = headers.get('Auto-Submitted', '').lower()
        if auto_submitted.startswith('auto'):
            if log is not None:
                log.info("Message discarded, automatic reply: %s" %
                         _log_message(headers))
            return _discarded

        # Check size against maximum
        if po.max_message_size:
            fname = fp.name
            if os.path.getsize(fname) > po.max_message_size:
                # XXX Bounce instead of discard? (Bounce emails user.)
                if log is not None:
                    log.info("Message discarded, exceeds max size limit: %s"
                             % _log_message(headers))
                return _discarded

        fp.seek(0)
        return wrapped(fp)

    return factory

_starts_with_whitespace = re.compile('^\s')

def _read_message_headers(fp):
    headers = {}
    header = None
    for line in fp:
        line = line.rstrip('\n').rstrip('\r')
        if not line:
            break
        if _starts_with_whitespace.match(line):
            headers[header] += line
            continue
        header, value = line.split(':', 1)
        headers[header] = value.strip()
    return headers
