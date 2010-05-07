from __future__ import with_statement

from cStringIO import StringIO
import unittest

class TestAPI(unittest.TestCase):
    def setUp(self):
        from repoze.postoffice import api
        self.tx = api.transaction = DummyTransaction()
        self.root = {}

    def _make_one(self, fp, queues=None, db_path='/postoffice', messages=None):
        from repoze.postoffice.api import PostOffice
        def dummy_open(fname):
            return fp
        po = PostOffice('postoffice.ini', DummyDB(self.root, queues, db_path),
                        dummy_open)
        if messages:
            po.Maildir, self.messages = DummyMaildirFactory(messages)
        return po

    def test_ctor_main_defaults(self):
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
        ))
        self.assertEqual(po.zodb_uri, 'filestorage:test.db')
        self.assertEqual(po.maildir, 'test/Maildir')
        self.assertEqual(po.zodb_path, '/postoffice')
        self.assertEqual(po.ooo_loop_frequency, 0)
        self.assertEqual(po.ooo_blackout_period, 300)
        self.assertEqual(po.max_message_size, 0)

    def test_ctor_main_everything(self):
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "zodb_path = /path/to/postoffice\n"
            "ooo_loop_frequency = 63\n"
            "ooo_blackout_period = 500\n"
            "max_message_size = 500mb\n"
        ))
        self.assertEqual(po.zodb_uri, 'filestorage:test.db')
        self.assertEqual(po.maildir, 'test/Maildir')
        self.assertEqual(po.zodb_path, '/path/to/postoffice')
        self.assertEqual(po.ooo_loop_frequency, 63)
        self.assertEqual(po.ooo_blackout_period, 500)
        self.assertEqual(po.max_message_size, 500 * 1<<20)

    def test_ctor_missing_main_section(self):
        self.assertRaises(
            ValueError, self._make_one, StringIO(
                "[some section]\n"
                "zodb_uri = zeo://localhost:666\n"
            )
        )

    def test_ctor_main_missing_required_parameter(self):
        self.assertRaises(
            ValueError, self._make_one, StringIO(
                "[post office]\n"
                "some_parameter = foo\n"
            )
        )

    def test_ctor_queues(self):
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            "[queue:B]\n"
            "filters =\n"
            "\tto_hostname:.exampleB.com\n"
        ))

        queues = po.configured_queues
        self.assertEqual(len(queues), 2)
        queue = queues.pop(0)
        self.assertEqual(queue['name'], 'A')
        self.assertEqual(len(queue['filters']), 1)
        self.assertEqual(queue['filters'][0].expr, 'exampleA.com')
        queue = queues.pop(0)
        self.assertEqual(queue['name'], 'B')
        self.assertEqual(len(queue['filters']), 1)
        self.assertEqual(queue['filters'][0].expr, '.exampleB.com')

    def test_ctor_bad_filtertype(self):
        self.assertRaises(ValueError, self._make_one, StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "filters =\n"
            "\tfoo:exampleA.com\n"
        ))

    def test_ctor_bad_queue_parameter(self):
        self.assertRaises(ValueError, self._make_one, StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "flutters =\n"
            "\tfoo:exampleA.com\n"
        ))

    def test_ctor_malformed_section(self):
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
        ))
        self.assertEqual(len(po.configured_queues), 0)

    def test_reconcile_queues_from_scratch(self):
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            "[queue:B]\n"
            "filters =\n"
            "\tto_hostname:.exampleB.com\n"
        ))
        self.failIf('postoffice' in self.root)
        po.reconcile_queues()
        self.failUnless('postoffice' in self.root)
        queues = self.root['postoffice']
        self.failUnless('A' in queues)
        self.failUnless('B' in queues)
        self.failUnless(self.tx.committed)

    def test_reconcile_queues_rm_old(self):
        log = DummyLogger()
        queues = {'foo': {}}
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
        ), queues)
        self.failIf('A' in queues)
        self.failUnless('foo' in queues)
        po.reconcile_queues(log)
        self.failUnless('A' in queues)
        self.failIf('foo' in queues)
        self.failUnless(self.tx.committed)
        self.assertEqual(len(log.infos), 2)

    def test_reconcile_queues_dont_remove_nonempty_queue(self):
        log = DummyLogger()
        queues = {'foo': {'bar': 'baz'}}
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
        ), queues)
        self.failIf('A' in queues)
        self.failUnless('foo' in queues)
        po.reconcile_queues(log)
        self.failUnless('A' in queues)
        self.failUnless('foo' in queues)
        self.assertEqual(len(log.warnings), 1)
        self.assertEqual(len(log.infos), 1)
        self.failUnless(self.tx.committed)

    def test_reconcile_queues_custom_db_path(self):
        queues = {}
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "zodb_path = /path/to/post/office\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            "[queue:B]\n"
            "filters =\n"
            "\tto_hostname:.exampleB.com\n"
        ), queues, '/path/to/post/office')
        self.failIf('A' in queues)
        self.failIf('B' in queues)
        po.reconcile_queues()
        self.failUnless('A' in queues)
        self.failUnless('B' in queues)
        self.failUnless(self.tx.committed)

    def test_context_manager_aborts_transaction_on_exception(self):
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
        ))
        try:
            with po._get_root() as root:
                raise Exception("Testing")
        except:
            pass
        self.failIf(self.tx.committed)
        self.failUnless(self.tx.aborted)

    def test_import_messages(self):
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg2 = DummyMessage("two")
        msg2['To'] = 'dummy@foo.exampleA.com'
        msg3 = DummyMessage("three")
        msg3['To'] = 'dummy@exampleB.com'
        msg4 = DummyMessage("four")
        msg4['To'] = 'dummy@foo.exampleb.com'

        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            "[queue:B]\n"
            "filters =\n"
            "\tto_hostname:.exampleB.com\n"
            ),
            queues=queues,
            messages=[msg1, msg2, msg3, msg4]
            )
        po.reconcile_queues()
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        A = queues['A']
        self.assertEqual(len(A), 1)
        self.assertEqual(A.pop_next(), 'one')
        B = queues['B']
        self.assertEqual(len(B), 2)
        self.assertEqual(B.pop_next(), 'three')
        self.assertEqual(B.pop_next(), 'four')
        self.assertEqual(len(log.infos), 5)

    def test_import_one_message(self):
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'

        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            ),
            queues=queues,
            messages=[msg1]
            )
        po.reconcile_queues()
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        A = queues['A']
        self.assertEqual(len(A), 1)
        self.assertEqual(A.pop_next(), 'one')
        self.assertEqual(len(log.infos), 2)

class Test_get_opt_int(unittest.TestCase):
    def _call_fut(self, dummy_config):
        from repoze.postoffice.api import _get_opt_int
        return _get_opt_int(dummy_config, None, None, None)

    def test_convert_to_int(self):
        self.assertEqual(self._call_fut(DummyConfig('10')), 10)

    def test_bad_int(self):
        self.assertRaises(ValueError, self._call_fut, DummyConfig('foo'))

class Test_get_opt_bytes(unittest.TestCase):
    def _call_fut(self, dummy_config):
        from repoze.postoffice.api import _get_opt_bytes
        return _get_opt_bytes(dummy_config, None, None, None)

    def test_convert_bytes(self):
        self.assertEqual(self._call_fut(DummyConfig('64')), 64)

    def test_convert_kilobytes(self):
        self.assertEqual(self._call_fut(DummyConfig('64K')), 64 * 1<<10)
        self.assertEqual(self._call_fut(DummyConfig('64kb')), 64 * 1<<10)

    def test_convert_megabytes(self):
        self.assertEqual(self._call_fut(DummyConfig('64m')), 64 * 1<<20)
        self.assertEqual(self._call_fut(DummyConfig('64MB')), 64 * 1<<20)

    def test_convert_gigabytes(self):
        self.assertEqual(self._call_fut(DummyConfig('64G')), 64 * 1<<30)
        self.assertEqual(self._call_fut(DummyConfig('64gb')), 64 * 1<<30)

    def test_bad_bytes(self):
        self.assertRaises(ValueError, self._call_fut, DummyConfig('64foos'))
        self.assertRaises(ValueError, self._call_fut, DummyConfig('sixty'))

class DummyConfig(object):
    def __init__(self, answer):
        self.answer = answer

    def get(self, section, name):
        return self.answer

    def has_option(self, section, name):
        return self.answer is not None

class DummyDB(object):
    def __init__(self, dbroot, queues, db_path):
        self.dbroot = dbroot
        self.queues = queues
        self.db_path = db_path.strip('/').split('/')

    def __call__(self, uri):
        return self

    def open(self):
        return self

    def root(self):
        node = self.dbroot
        for name in self.db_path[:-1]:
            node[name] = {}
            node = node[name]
        node[self.db_path[-1]] = self.queues
        return self.dbroot

class DummyLogger(object):
    def __init__(self):
        self.warnings = []
        self.infos = []

    def warn(self, msg):
        self.warnings.append(msg)

    def info(self, msg):
        self.infos.append(msg)

class DummyTransaction(object):
    committed = False
    aborted = False

    def commit(self):
        self.committed = True

    def abort(self):
        self.aborted = True

def DummyMaildirFactory(messages):
    messages = dict(zip(xrange(len(messages)), messages))

    class DummyMaildir(object):
        def __init__(self, path, factory, create):
            self.path = path
            self.factory = factory
            self.create = create
            self.folders = {}

        def keys(self):
            return range(len(messages))

        def get_message(self, key):
            return messages[key]

        def remove(self, key):
            del messages[key]

        def get_folder(self, name):
            if name not in self.folders:
                from mailbox import NoSuchMailboxError
                raise NoSuchMailboxError(name)
            return self.folders[name]

        def add_folder(self, name):
            folder = self.folders[name] = set()
            return folder

    return DummyMaildir, messages

from repoze.postoffice.message import Message
class DummyMessage(Message):
    def __init__(self, body=None):
        Message.__init__(self)
        self.set_payload(body)
        self['From'] = 'Woody Woodpecker <ww@toonz.net>'
        self['Subject'] = 'Double date tonight'
        self['Message-Id'] = '12389jdfkj98'

    def __eq__(self, other):
        return self.get_payload().__eq__(other)

    def __hash__(self):
        return hash(self.get_payload())
