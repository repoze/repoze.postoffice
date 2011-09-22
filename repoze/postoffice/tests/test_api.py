from __future__ import with_statement

from cStringIO import StringIO
import unittest

class TestAPI(unittest.TestCase):
    def setUp(self):
        from repoze.postoffice import api
        self.tx = api.transaction = DummyTransaction()
        self.root = {}

        import tempfile
        self.tempfolder = tempfile.mkdtemp('repoze.postoffice.tests')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tempfolder)

    def _make_one(self, fp, queues=None, db_path='/postoffice', messages=None):
        from repoze.postoffice.api import PostOffice
        import os
        import tempfile

        def dummy_open(fname):
            return fp
        po = PostOffice('postoffice.ini', DummyDB(self.root, queues, db_path),
                        dummy_open)
        po.Queue = DummyQueue
        if messages:
            def mk_message(msg):
                fd, fname = tempfile.mkstemp(dir=self.tempfolder)
                writer = os.fdopen(fd,  'w')
                writer.write(msg.as_string())
                writer.close()
                return open(fname)
            messages = map(mk_message, messages)
            po.Maildir, self.messages = DummyMaildirFactory(messages)
            po.MaildirMessage = DummyMessage
        return po

    def test_ctor_main_defaults(self):
        from datetime import timedelta
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
        ))
        self.assertEqual(po.zodb_uri, 'filestorage:test.db')
        self.assertEqual(po.maildir, 'test/Maildir')
        self.assertEqual(po.zodb_path, '/postoffice')
        self.assertEqual(po.ooo_loop_frequency, 0)
        self.assertEqual(po.ooo_loop_headers, [])
        self.assertEqual(po.ooo_throttle_period, timedelta(minutes=5))
        self.assertEqual(po.max_message_size, 0)

    def test_ctor_main_everything(self):
        from datetime import timedelta
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "zodb_path = /path/to/postoffice\n"
            "ooo_loop_frequency = 63\n"
            "ooo_loop_headers = A, B\n"
            "ooo_throttle_period = 500\n"
            "max_message_size = 500mb\n"
        ))
        self.assertEqual(po.zodb_uri, 'filestorage:test.db')
        self.assertEqual(po.maildir, 'test/Maildir')
        self.assertEqual(po.zodb_path, '/path/to/postoffice')
        self.assertEqual(po.ooo_loop_frequency, 63)
        self.assertEqual(po.ooo_loop_headers, ['A', 'B'])
        self.assertEqual(po.ooo_throttle_period, timedelta(seconds=500))
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

    def test_ctor_filters(self):
        import pkg_resources
        import re
        header_checks = pkg_resources.resource_filename(
            'repoze.postoffice.tests', 'test_header_regexps.txt')
        body_checks = pkg_resources.resource_filename(
            'repoze.postoffice.tests', 'test_body_regexps.txt')
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            "\theader_regexp: Subject: You are nice\n"
            "\theader_regexp_file: %(header_checks)s\n"
            "\tbody_regexp: I like you\n"
            "\tbody_regexp_file: %(body_checks)s\n" % {
                'header_checks': header_checks,
                'body_checks': body_checks}
        ))

        queues = po.configured_queues
        self.assertEqual(len(queues), 1)
        queue = queues.pop(0)
        filters = queue['filters']
        self.assertEqual(len(filters), 5)
        self.assertEqual(filters[0].expr, 'exampleA.com')
        def p(s, additional_flags=0):
            return (s, re.compile(s, re.IGNORECASE | additional_flags))
        self.assertEqual(filters[1].regexps, [p(u'Subject: You are nice')])
        self.assertEqual(filters[2].regexps, [p(u'Subject: Nice to meet you'),
                                              p(u'Subject: You are nice')])
        self.assertEqual(filters[3].regexps, [p(u'I like you', re.MULTILINE),])
        self.assertEqual(filters[4].regexps, [p(u'Nice to meet you',
                                                re.MULTILINE),
                                              p(u'You are nice', re.MULTILINE)])

    def test_ctor_global_reject_filters(self):
        import pkg_resources
        import re
        header_checks = pkg_resources.resource_filename(
            'repoze.postoffice.tests', 'test_header_regexps.txt')
        body_checks = pkg_resources.resource_filename(
            'repoze.postoffice.tests', 'test_body_regexps.txt')
        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "reject_filters =\n"
            "\tto_hostname:exampleA.com\n"
            "\theader_regexp: Subject: You are nice\n"
            "\theader_regexp_file: %(header_checks)s\n"
            "\tbody_regexp: I like you\n"
            "\tbody_regexp_file: %(body_checks)s\n" % {
                'header_checks': header_checks,
                'body_checks': body_checks}
        ))

        filters = po.reject_filters
        self.assertEqual(len(filters), 5)
        self.assertEqual(filters[0].expr, 'exampleA.com')
        def p(s, additional_flags=0):
            return (s, re.compile(s, re.IGNORECASE | additional_flags))
        self.assertEqual(filters[1].regexps, [p(u'Subject: You are nice')])
        self.assertEqual(filters[2].regexps, [p(u'Subject: Nice to meet you'),
                                              p(u'Subject: You are nice')])
        self.assertEqual(filters[3].regexps, [p(u'I like you', re.MULTILINE)])
        self.assertEqual(filters[4].regexps, [p(u'Nice to meet you',
                                                re.MULTILINE),
                                              p(u'You are nice', re.MULTILINE)])

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
        m = A.pop_next()
        self.assertEqual(m, 'one')
        self.assertTrue(int(m['X-Postoffice-Date']))
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
            "max_message_size = 5mb\n"
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

    def test_import_message_too_big(self):
        log = DummyLogger()
        msg1 = DummyMessage("ha ha ha ha")
        msg1['To'] = 'dummy@exampleA.com'

        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "max_message_size = 10\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            ),
            queues=queues,
            messages=[msg1]
            )
        po.reconcile_queues()
        po.import_messages(log)
        A = queues['A']
        self.assertEqual(len(A), 1)
        self.assertEqual(A[0]['X-Postoffice-Rejected'],
                         'Maximum Message Size Exceeded')
        self.failUnless(A[0].get_payload().startswith(
            'Message body discarded.'))
        self.assertEqual(len(log.infos), 3)

    def test_import_message_is_duplicate(self):
        log = DummyLogger()
        msg1 = DummyMessage("ha ha ha ha")
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
        A = queues['A']
        A.duplicate = True
        po.import_messages(log)
        self.assertEqual(len(A), 0)
        self.assertEqual(len(log.infos), 2)

    def test_import_message_malformed_date(self):
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg1['Date'] = 'Mon, 32 Jun 2011 14:44:21 -0000'

        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "max_message_size = 5mb\n"
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

    def test_import_message_auto_reply_precedence_header(self):
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg1['Precedence'] = 'bulk'

        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "max_message_size = 5mb\n"
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
        self.assertEqual(A[0]['X-Postoffice-Rejected'], 'Auto-response')
        self.assertEqual(len(log.infos), 3, log.infos)

    def test_import_message_auto_reply_rfc3834(self):
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg1['Auto-Submitted'] = 'Auto-Submitted'

        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "max_message_size = 5mb\n"
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
        self.assertEqual(A[0]['X-Postoffice-Rejected'], 'Auto-response')
        self.assertEqual(len(log.infos), 3)

    def test_user_throttled(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg1['Date'] = 'Wed, 12 May 2010 02:42:00'
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
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        A.throttled = True
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(A), 1)
        self.assertEqual(A[0]['X-Postoffice-Rejected'], 'Throttled')
        self.assertEqual(len(log.infos), 3)

    def test_throttle_user_instant_freq(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg1['Date'] = 'Wed, 12 May 2010 02:42:00'
        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "ooo_loop_frequency = 0.25\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            ),
            queues=queues,
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        A.instant_freq = 1
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(A), 1)
        self.assertEqual(A[0]['X-Postoffice-Rejected'], 'Throttled')
        self.assertEqual(len(log.infos), 3)
        self.assertEqual(A.throttled, datetime.datetime(2010, 5, 12, 2, 47))

    def test_throttle_user_average_freq(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg1['Date'] = 'Wed, 12 May 2010 02:42:00'
        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "ooo_loop_frequency = 0.25\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            ),
            queues=queues,
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        A.average_freq = 1
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(A), 1)
        self.assertEqual(A[0]['X-Postoffice-Rejected'], 'Throttled')
        self.assertEqual(len(log.infos), 3)
        self.assertEqual(A.throttled, datetime.datetime(2010, 5, 12, 2, 47))
        self.assertEqual(A.interval, datetime.timedelta(minutes=16.0))

    def test_throttle_passes_headers(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg1['Date'] = 'Wed, 12 May 2010 02:42:00'
        msg1['A'] = 'foo'
        msg1['B'] = 'bar'
        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "ooo_loop_frequency = 0.25\n"
            "ooo_loop_headers = A, B\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            ),
            queues=queues,
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        po.import_messages(log)
        self.assertEqual(A.match_headers, {'A': 'foo', 'B': 'bar'})

    def test_missing_from(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        del msg1['From']
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
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(A), 0)
        self.assertEqual(len(log.infos), 2)

    def test_missing_message_id(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        del msg1['Message-Id']
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
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(A), 0)
        self.assertEqual(len(log.infos), 2)

    def test_incoming_bounce_message(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'dummy@exampleA.com'
        msg1['X-Postoffice'] = 'Bounced'
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
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(A), 0)
        self.assertEqual(len(log.infos), 2)

    def test_from_and_to_identical(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        del msg1['From']
        msg1['From'] = msg1['To'] = 'dummy@exampleA.com'
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
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(A), 0)
        self.assertEqual(len(log.infos), 2)


    def test_rejected_by_filter(self):
        import datetime
        log = DummyLogger()
        msg1 = DummyMessage("one")
        msg1['To'] = 'daffy@exampleA.com'
        queues = {}

        po = self._make_one(StringIO(
            "[post office]\n"
            "zodb_uri = filestorage:test.db\n"
            "maildir = test/Maildir\n"
            "reject_filters = \n"
            "\theader_regexp: From:.+woody\n"
            "[queue:A]\n"
            "filters =\n"
            "\tto_hostname:exampleA.com\n"
            ),
            queues=queues,
            messages=[msg1,]
            )
        po.reconcile_queues()
        A = queues['A']
        po.import_messages(log)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(A), 0)
        self.assertEqual(len(log.infos), 2)

class Test_get_opt_int(unittest.TestCase):
    def _call_fut(self, dummy_config):
        from repoze.postoffice.api import _get_opt_int
        return _get_opt_int(dummy_config, None, None, None)

    def test_convert_to_int(self):
        self.assertEqual(self._call_fut(DummyConfig('10')), 10)

    def test_bad_int(self):
        self.assertRaises(ValueError, self._call_fut, DummyConfig('foo'))

class Test_get_opt_float(unittest.TestCase):
    def _call_fut(self, dummy_config):
        from repoze.postoffice.api import _get_opt_float as fut
        return fut(dummy_config, None, None, None)

    def test_convert_to_float(self):
        self.assertEqual(self._call_fut(DummyConfig('10.5')), 10.5)

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

class Test_send_mail(unittest.TestCase):
    def test_string_message(self):
        from repoze.postoffice.api import _send_mail as fut
        smtp = DummySMTPLib()
        fut('me', ['you', 'them'], 'Hello', smtplib=smtp)
        self.assertEqual(smtp.sent, [('me', ['you', 'them'], 'Hello'),])

    def test_message_object(self):
        from repoze.postoffice.api import _send_mail as fut
        smtp = DummySMTPLib()
        message = DummyMessage('Hello')
        fut('me', ['you', 'them'], message, smtplib=smtp)
        self.assertEqual(smtp.sent, [('me', ['you', 'them'],
                                      message.as_string()),])

class Test_read_message_headers(unittest.TestCase):
    def test_it(self):
        message = (
            "From: me\n"
            "To: you\n"
            " and your mom\n"
            "Subject: Hello\n"
            "\n"
            "Hi mate.\n"
            "\n"
        )
        from cStringIO import StringIO
        fp = StringIO(message)

        from repoze.postoffice.api import _read_message_headers as fut
        expected = dict(
            From='me',
            To='you and your mom',
            Subject='Hello',
        )
        self.assertEqual(fut(fp), expected)

class DummySMTPLib(object):
    def __init__(self):
        self.sent = []

    def SMTP(self, host):
        return self

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent.append((from_addr, to_addrs, msg))

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
        self.opened = False
        self.closed = False

    def __call__(self, uri):
        return self

    def open(self):
        self.opened = True
        return self

    def root(self):
        node = self.dbroot
        for name in self.db_path[:-1]:
            node[name] = {}
            node = node[name]
        node[self.db_path[-1]] = self.queues
        return self.dbroot

    def close(self):
        self.closed = True

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
            return self.factory(messages[key])

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

from mailbox import MaildirMessage
class DummyMessage(MaildirMessage):
    def __init__(self, body=None):
        if isinstance(body, file):
            MaildirMessage.__init__(self, body)
        else:
            MaildirMessage.__init__(self)
            self.set_payload(body)
            self['From'] = 'Woody Woodpecker <ww@toonz.net>'
            self['Subject'] = 'Double date tonight'
            self['Message-Id'] = '12389jdfkj98'

    def __eq__(self, other):
        return self.get_payload().__eq__(other)

    def __hash__(self):
        return hash(self.get_payload())

class DummyQueue(list):
    throttled = False
    instant_freq = 0
    average_freq = 0
    interval = None
    match_headers = None
    duplicate = False

    def add(self, message):
        self.append(message)

    def pop_next(self):
        return self.pop(0)

    def throttle(self, user, until, headers):
        self.throttled = until

    def is_throttled(self, user, now, headers):
        return self.throttled

    def get_instantaneous_frequency(self, user, now, headers):
        self.match_headers = headers
        return self.instant_freq

    def get_average_frequency(self, user, now, interval, headers):
        self.interval = interval
        self.match_headers = headers
        return self.average_freq

    def collect_frequency_data(self, message, headers):
        pass

    def is_duplicate(self, message):
        return self.duplicate
