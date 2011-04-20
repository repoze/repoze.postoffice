from __future__ import with_statement

from code import interact
from optparse import OptionParser
from repoze.postoffice.api import PostOffice
import logging
import os
import sys

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s: %(message)s')


class ConsoleScript(object):
    """
    Populates postoffice queues from a Maildir.
    """

    def __init__(self, argv=sys.argv[1:], find_config=None):
        parser = OptionParser(description=self.__doc__)
        parser.add_option('-C', '--config', dest='config', default=None,
                          help='Path to configuration ini file.',
                          metavar='FILE')
        parser.add_option('-v', '--verbose', dest='verbose', default=False,
                          action='store_true',
                          help='Print info level log messages')

        options, args = parser.parse_args(argv)
        if args:
            parser.error('Extra arguments given.')

        config = options.config
        if config is None:
            config = _find_config()
        if config is None:
            parser.error('Unable to find configuration file.')

        log_level = logging.WARN
        if options.verbose:
            log_level = logging.INFO
        self.log = logging.getLogger('repoze.postoffice')
        self.log.setLevel(log_level)
        self.config = config

    def __call__(self):
        po = PostOffice(self.config)
        po.reconcile_queues(self.log)
        po.import_messages(self.log)

    def debug(self):
        po = PostOffice(self.config)
        banner = '"root" is the root queues folder.'
        with po._get_root() as root:
            interact(banner, local={'root':root})

def _find_config():
    path = os.path.abspath('postoffice.ini')
    if os.path.exists(path):
        return path

    path = os.path.join(os.path.abspath('etc'), 'postoffice.ini')
    if os.path.exists(path):
        return path

    base = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
    path = os.path.join(base, 'etc', 'postoffice.ini')
    if os.path.exists(path):
        return path

    path = '/etc/postoffice.ini'
    if os.path.exists(path):
        return path

def main():
    return ConsoleScript()()

def debug():
    return ConsoleScript().debug()

if __name__ == '__main__':
    main()
