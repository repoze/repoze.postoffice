from __future__ import with_statement

from cStringIO import StringIO
from ConfigParser import ConfigParser
from contextlib import contextmanager
import logging
from mailbox import Maildir
import os
import shutil
import transaction

from repoze.postoffice.filters import ToHostnameFilter
from repoze.postoffice.queue import QueuesFolder
from repoze.postoffice.queue import Queue
from repoze.zodbconn.uri import db_from_uri

MAIN_SECTION = 'post office'
_marker = object()

log = logging.getLogger('repoze.postoffice')

class PostOffice(object):
    """
    Provides server side API for repoze.postoffice.
    """

    # Overridable for testing
    Maildir = Maildir

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
        self.ooo_loop_frequency = _get_opt_int(
            config, MAIN_SECTION, 'ooo_loop_frequency', '0')
        self.ooo_blackout_period = _get_opt_int(
            config, MAIN_SECTION, 'ooo_blackout_period', '300')
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
            elif option =='here':
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

    def reconcile_queues(self):
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
                    root[name] = Queue()

            # Remove old queues if empty
            configured_names = set([q['name'] for q in configured])
            for name, queue in root.items():
                if name not in configured_names:
                    if len(queue):
                        log.warn(
                            "Queue removed from configuration still has "
                            "messages: %s" % name
                        )
                    else:
                        del root[name]

    def import_messages(self):
        """
        Imports messages from an external maildir, matches them to queues and
        either stores or discards each message depending on whether it matches
        a queue definition.  Once a message is imported it is removed from the
        maildir.
        """
        maildir = self.Maildir(self.maildir, factory=None, create=True)
        keys = list(maildir.keys())
        keys.sort()
        for key in keys:
            self._import_message(maildir.get_message(key))
            maildir.remove(key)

    def _import_message(self, message):
        for configured in self.configured_queues:
            filters = configured['filters']
            if not filters or not _filters_match(filters, message):
                continue

            # Matches queue
            with self._get_root() as queues:
                queue = queues[configured['name']]
                queue.add(message)


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
