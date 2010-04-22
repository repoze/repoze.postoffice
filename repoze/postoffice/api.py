from cStringIO import StringIO
from ConfigParser import ConfigParser
import os
import shutil

from repoze.postoffice.filters import ToHostnameFilter

MAIN_SECTION = 'post office'
_marker = object()

class PostOffice(object):
    """
    Provides server side API for repoze.postoffice.
    """
    def __init__(self, fp):
        """
        Initialize from configuration file.
        """
        fp = _load_fp(fp)
        self._section_indices = _get_section_indices(fp)
        fp.seek(0)
        config = ConfigParser()
        config.readfp(fp)
        self._init_main_section(config)
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
            else:
                raise ValueError('Unknown config parameter for queue: %s' %
                                 option)

        return dict(name=name, filters=filters, section=section)

    def _init_filter(self, filter_):
        name, config = filter_.split(':')
        if name == 'to_hostname':
            return ToHostnameFilter(config.strip())

        raise ValueError("Unknown filter type: %s" % name)

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
