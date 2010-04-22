from cStringIO import StringIO
import unittest

class TestAPI(unittest.TestCase):
    def _make_one(self, fp):
        from repoze.postoffice.api import PostOffice
        return PostOffice(fp)

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
