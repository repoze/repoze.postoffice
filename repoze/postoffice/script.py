from optparse import OptionParser
from repoze.postoffice.api import PostOffice
import os
import sys

class ConsoleScript(object):
    """
    Populates postoffice queues from a Maildir.
    """

    def __init__(self, argv=sys.argv[1:], find_config=None):
        parser = OptionParser(description=self.__doc__)
        parser.add_option('-C', '--config', dest='config', default=None,
                          help='Path to configuration ini file.',
                          metavar='FILE')
        options, args = parser.parse_args(argv)
        if args:
            parser.error('Extra arguments given.')

        config = options.config
        if config is None:
            config = _find_config()
        if config is None:
            parser.error('Unable to find configuration file.')

        self.config = config

    def __call__(self):
        po = PostOffice(self.config)
        po.reconcile_queues()
        po.import_messages()


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

if __name__ == '__main__':
    main()
