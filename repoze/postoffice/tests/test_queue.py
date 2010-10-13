import unittest

class TestQueue(unittest.TestCase):
    def setUp(self):
        from repoze.postoffice import queue
        self._save_datetime = queue.datetime
        self._dummy_datetime = DummyDatetime()
        queue.datetime = self._dummy_datetime

    def tearDown(self):
        from repoze.postoffice import queue
        queue.datetime = self._save_datetime

    def _make_one(self):
        from repoze.postoffice.queue import Queue
        return Queue()

    def _set_now(self, now):
        self._dummy_datetime._now = now

    def test_add_and_retrieve_messages(self):
        queue = self._make_one()
        queue.add(DummyMessage('one'))
        self.assertEqual(len(queue), 1)
        self.failUnless(queue)
        queue.add(DummyMessage('two'))
        self.assertEqual(len(queue), 2)
        self.assertEqual(queue.pop_next(), 'one')
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue.pop_next(), 'two')
        self.assertEqual(len(queue), 0)
        self.failIf(queue)

    def test_is_duplicate_false(self):
        queue = self._make_one()
        message = DummyMessage('one')
        self.failIf(queue.is_duplicate(message))

    def test_is_duplicate_bbb_persistence(self):
        queue = self._make_one()
        del queue._message_ids
        message = DummyMessage('one')
        self.failIf(queue.is_duplicate(message))

    def test_is_duplicate_true(self):
        queue = self._make_one()
        message = DummyMessage('one')
        queue.add(message)
        self.failUnless(queue.is_duplicate(message))

    def test_is_duplicate_past_cutoff(self):
        import time
        queue = self._make_one()
        message = DummyMessage('one')
        timestamp = time.time() - 30 * 60 * 60
        queue._message_ids[message['Message-Id']] = timestamp
        self.failIf(queue.is_duplicate(message))

    def test_bounce_generic_message(self):
        import base64
        from repoze.postoffice.message import Message
        class DummySend(object):
            def __init__(self):
                self.sent = []
            def __call__(self, fromaddr, toaddrs, message):
                self.sent.append((fromaddr, toaddrs, message))

        bounced = Message()
        bounced['To'] = 'Submissions <submissions@example.com>'
        bounced['From'] = 'Chris Rossi <chris@example.com>'
        bounced['Date'] = 'Last Tuesday'
        queue = self._make_one()
        send = DummySend()
        queue.bounce(bounced, send, 'Bouncer <bouncer@example.com>')

        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, message = send.sent[0]
        self.assertEqual(fromaddr, 'Bouncer <bouncer@example.com>')
        self.assertEqual(message['From'], 'Bouncer <bouncer@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(message['To'], 'Chris Rossi <chris@example.com>')
        self.failUnless(message['Subject'].startswith(
            'Your message to Submissions'), message['Subject'])
        self.assertEqual(message['X-Postoffice'], 'Bounced')
        body = base64.b64decode(message.get_payload())
        self.failUnless('has bounced' in body, body)
        self.failUnless('Last Tuesday' in body, body)

    def test_bounce_reason_and_bounce_message(self):
        queue = self._make_one()
        self.assertRaises(ValueError, queue.bounce, None, None, 'x@y.it',
                          object(), object())

    def test_bounce_reason(self):
        import base64
        from repoze.postoffice.message import Message
        class DummySend(object):
            def __init__(self):
                self.sent = []
            def __call__(self, fromaddr, toaddrs, message):
                self.sent.append((fromaddr, toaddrs, message))

        bounced = Message()
        bounced['To'] = 'Submissions <submissions@example.com>'
        bounced['From'] = 'Chris Rossi <chris@example.com>'
        queue = self._make_one()
        send = DummySend()
        queue.bounce(bounced, send, 'Bouncer <bouncer@example.com>',
                     'Not entertaining enough.')

        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, message = send.sent[0]
        self.assertEqual(fromaddr, 'Bouncer <bouncer@example.com>')
        self.assertEqual(message['From'], 'Bouncer <bouncer@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(message['To'], 'Chris Rossi <chris@example.com>')
        self.failUnless(message['Subject'].startswith(
            'Your message to Submissions'), message['Subject'])
        self.assertEqual(message['X-Postoffice'], 'Bounced')
        body = base64.b64decode(message.get_payload())
        self.failUnless('Not entertaining enough.' in body, body)

    def test_bounce_custom_message(self):
        import base64
        from repoze.postoffice.message import Message
        class DummySend(object):
            def __init__(self):
                self.sent = []
            def __call__(self, fromaddr, toaddrs, message):
                self.sent.append((fromaddr, toaddrs, message))

        bounced = Message()
        bounced['To'] = 'Submissions <submissions@example.com>'
        bounced['From'] = 'Chris Rossi <chris@example.com>'
        queue = self._make_one()
        send = DummySend()
        bounce_message = Message()
        bounce_message.set_payload('TEST')
        queue.bounce(bounced, send, 'Bouncer <bouncer@example.com>',
                     bounce_message=bounce_message)

        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, message = send.sent[0]
        self.assertEqual(fromaddr, 'Bouncer <bouncer@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(message.get_payload(), 'TEST')
        self.assertEqual(message['X-Postoffice'], 'Bounced')

    def test_bounce_reason_unicode(self):
        import base64
        from repoze.postoffice.message import Message
        class DummySend(object):
            def __init__(self):
                self.sent = []
            def __call__(self, fromaddr, toaddrs, message):
                self.sent.append((fromaddr, toaddrs, message))

        bounced = Message()
        bounced['To'] = 'Submissions <submissions@example.com>'
        bounced['From'] = 'Chris Rossi <chris@example.com>'
        queue = self._make_one()
        send = DummySend()
        queue.bounce(bounced, send, 'Bouncer <bouncer@example.com>',
                     u'Not entertaining eno\xfagh.')

        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, message = send.sent[0]
        self.assertEqual(fromaddr, 'Bouncer <bouncer@example.com>')
        self.assertEqual(message['From'], 'Bouncer <bouncer@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(message['To'], 'Chris Rossi <chris@example.com>')
        self.failUnless(message['Subject'].startswith(
            'Your message to Submissions'), message['Subject'])
        self.assertEqual(message['X-Postoffice'], 'Bounced')
        body = base64.b64decode(message.get_payload())
        self.failUnless(
            u'Not entertaining eno\xfagh.'.encode('UTF-8') in body, body
        )

    def test_bounce_sender_unicode(self):
        import base64
        from repoze.postoffice.message import Message
        class DummySend(object):
            def __init__(self):
                self.sent = []
            def __call__(self, fromaddr, toaddrs, message):
                self.sent.append((fromaddr, toaddrs, message))

        bounced = Message()
        bounced['To'] = 'Submissions <submissions@example.com>'
        bounced['From'] = 'Chris Rossi <chris@example.com>'
        queue = self._make_one()
        send = DummySend()
        queue.bounce(bounced, send, u'Bounc\xe9r <bouncer@example.com>',
                     'Not entertaining enough.')

        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, message = send.sent[0]
        self.assertEqual(fromaddr, u'Bounc\xe9r <bouncer@example.com>')
        self.assertEqual(message['From'], u'Bounc\xe9r <bouncer@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(message['To'], 'Chris Rossi <chris@example.com>')
        self.failUnless(message['Subject'].startswith(
            'Your message to Submissions'), message['Subject'])
        self.assertEqual(message['X-Postoffice'], 'Bounced')
        body = base64.b64decode(message.get_payload())
        self.failUnless('Not entertaining enough.' in body, body)

    def test_quarantine(self):
        queue = self._make_one()
        queue.quarantine(DummyMessage('Oh nos!'), ('OMG', 'WTH', '???'))
        queue.quarantine(DummyMessage('Woopsy!'), ('IRCC', 'FWIW', 'ROTFLMAO'))
        msgs = list(queue.get_quarantined_messages())
        self.assertEqual(len(msgs), 2)
        msg, error = msgs.pop(0)
        self.assertEqual(msg, 'Oh nos!')
        self.assertEqual(error, ('OMG', 'WTH', '???'))
        msg, error = msgs.pop(0)
        self.assertEqual(msg, 'Woopsy!')
        self.assertEqual(error, ('IRCC', 'FWIW', 'ROTFLMAO'))
        self.assertEqual(
            queue.get_quarantined_message(msg['X-Postoffice-Id']), msg
        )

    def test_quarantine_notice_missing_fromaddr(self):
        queue = self._make_one()
        self.assertRaises(ValueError, queue.quarantine,
                          None, None, object(), None)

    def test_quarantine_notice(self):
        import base64
        from repoze.postoffice.message import Message
        class DummySend(object):
            def __init__(self):
                self.sent = []
            def __call__(self, fromaddr, toaddrs, message):
                self.sent.append((fromaddr, toaddrs, message))

        message = Message()
        message['To'] = 'Submissions <submissions@example.com>'
        message['From'] = 'Chris Rossi <chris@example.com>'
        queue = self._make_one()
        send = DummySend()
        queue.quarantine(message, (None, None, None), send,
                         'Oopsy Daisy <error@example.com>')
        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, notice = send.sent[0]
        self.assertEqual(fromaddr, 'Oopsy Daisy <error@example.com>')
        self.assertEqual(notice['From'], 'Oopsy Daisy <error@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(notice['To'], 'Chris Rossi <chris@example.com>')
        self.failUnless(notice['Subject'].startswith('An error has occurred'))
        self.assertEqual(notice['X-Postoffice'], 'Bounced')
        body = base64.b64decode(notice.get_payload())
        self.failUnless('System administrators have been informed' in body)


    def test_quarantine_notice_unicode_sender(self):
        import base64
        from repoze.postoffice.message import Message
        class DummySend(object):
            def __init__(self):
                self.sent = []
            def __call__(self, fromaddr, toaddrs, message):
                self.sent.append((fromaddr, toaddrs, message))

        message = Message()
        message['To'] = 'Submissions <submissions@example.com>'
        message['From'] = u'Chris Ross\xed <chris@example.com>'
        queue = self._make_one()
        send = DummySend()
        queue.quarantine(message, (None, None, None), send,
                         u'Oopsy Daisy <error@example.com>')
        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, notice = send.sent[0]
        self.assertEqual(fromaddr, 'Oopsy Daisy <error@example.com>')
        self.assertEqual(notice['From'], 'Oopsy Daisy <error@example.com>')
        self.assertEqual(toaddrs, [u'Chris Ross\xed <chris@example.com>'])
        self.assertEqual(notice['To'], u'Chris Ross\xed <chris@example.com>')
        self.failUnless(notice['Subject'].startswith('An error has occurred'))
        self.assertEqual(notice['X-Postoffice'], 'Bounced')
        body = base64.b64decode(notice.get_payload())
        self.failUnless('System administrators have been informed' in body)

    def test_quarantine_notice_w_date(self):
        import base64
        from repoze.postoffice.message import Message
        class DummySend(object):
            def __init__(self):
                self.sent = []
            def __call__(self, fromaddr, toaddrs, message):
                self.sent.append((fromaddr, toaddrs, message))

        message = Message()
        message['To'] = 'Submissions <submissions@example.com>'
        message['From'] = 'Chris Rossi <chris@example.com>'
        message['Date'] = 'Last Tuesday'
        queue = self._make_one()
        send = DummySend()
        queue.quarantine(message, (None, None, None), send,
                         'Oopsy Daisy <error@example.com>')
        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, notice = send.sent[0]
        self.assertEqual(fromaddr, 'Oopsy Daisy <error@example.com>')
        self.assertEqual(notice['From'], 'Oopsy Daisy <error@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(notice['To'], 'Chris Rossi <chris@example.com>')
        self.failUnless(notice['Subject'].startswith('An error has occurred'))
        self.assertEqual(notice['X-Postoffice'], 'Bounced')
        body = base64.b64decode(notice.get_payload())
        self.failUnless('System administrators have been informed' in body)
        self.failUnless('Last Tuesday' in body)

    def test_remove_from_quarantine(self):
        msg = DummyMessage('Oops, my bad.')
        queue = self._make_one()
        queue.quarantine(DummyMessage('Oh nos!'), ('OMG', 'WTH', '???'))
        queue.quarantine(msg, (None, None, None))
        queue.quarantine(DummyMessage('Woopsy!'), ('IRCC', 'FWIW', 'ROTFLMAO'))
        msgs = list(queue.get_quarantined_messages())
        self.assertEqual(len(msgs), 3)
        queue.remove_from_quarantine(msg)
        msgs = list(queue.get_quarantined_messages())
        self.assertEqual(len(msgs), 2)
        msg, error = msgs.pop(0)
        self.assertEqual(msg, 'Oh nos!')
        self.assertEqual(error, ('OMG', 'WTH', '???'))
        msg, error = msgs.pop(0)
        self.assertEqual(msg, 'Woopsy!')
        self.assertEqual(error, ('IRCC', 'FWIW', 'ROTFLMAO'))

    def test_remove_from_quarantine_not_in_quarantine(self):
        msg = DummyMessage('Oops, my bad')
        queue = self._make_one()
        queue.quarantine(msg, (None, None, None))
        self.assertEqual(queue.count_quarantined_messages(), 1)
        queue.remove_from_quarantine(msg)
        self.assertEqual(queue.count_quarantined_messages(), 0)
        self.assertRaises(ValueError, queue.remove_from_quarantine, msg)

    def test_remove_from_quarantine_bad_id(self):
        msg = DummyMessage('Oops, my bad')
        queue = self._make_one()
        queue.quarantine(msg, (None, None, None))
        self.assertEqual(queue.count_quarantined_messages(), 1)
        id = msg['X-Postoffice-Id']
        queue.remove_from_quarantine(msg)
        msg['X-Postoffice-Id'] = id
        self.assertEqual(queue.count_quarantined_messages(), 0)
        self.assertRaises(ValueError, queue.remove_from_quarantine, msg)

    def test_requeue_quarantined_messages(self):
        msg = DummyMessage('Oops, my bad.')
        queue = self._make_one()
        queue.quarantine(DummyMessage('Oh nos!'), ('OMG', 'WTH', '???'))
        queue.quarantine(msg, (None, None, None))
        queue.quarantine(DummyMessage('Woopsy!'), ('IRCC', 'FWIW', 'ROTFLMAO'))
        self.assertEqual(len(queue), 0)
        self.assertEqual(len(list(queue.get_quarantined_messages())), 3)
        queue.requeue_quarantined_messages()
        self.assertEqual(len(queue), 3)
        self.assertEqual(len(list(queue.get_quarantined_messages())), 0)

    def test_get_instantaneous_frequency(self):
        from datetime import datetime
        now = datetime(2010, 5, 13, 2, 42, 30)
        queue = self._make_one()
        fut = queue.get_instantaneous_frequency
        self.assertAlmostEqual(fut('Harry', now), 0.0)
        message = DummyMessage('one')
        message['Date'] = 'Wed, 13 May 2010 02:42:00'
        queue.collect_frequency_data(message)
        self.assertAlmostEqual(fut('Harry', now), 2.0)
        now = datetime(2010, 5, 13, 2, 46)
        self.assertAlmostEqual(fut('Harry', now), 0.25)

    def test_get_instantaneous_frequency_infinite(self):
        from datetime import datetime
        now = datetime(2010, 5, 13, 2, 42, 00)
        queue = self._make_one()
        fut = queue.get_instantaneous_frequency
        self.assertAlmostEqual(fut('Harry', now), 0.0)
        message = DummyMessage('one')
        message['Date'] = 'Wed, 13 May 2010 02:42:00'
        queue.collect_frequency_data(message)
        self.assertEqual(fut('Harry', now), float('inf'))

    def test_get_instantaneous_filtered(self):
        from datetime import datetime
        now = datetime(2010, 5, 13, 2, 42, 30)
        queue = self._make_one()
        fut = queue.get_instantaneous_frequency
        self.assertAlmostEqual(fut('Harry', now), 0.0)

        message = DummyMessage('one')
        message['Date'] = 'Wed, 13 May 2010 02:42:00'
        message['A'] = 'foo'
        message['B'] = 'bar'
        queue.collect_frequency_data(message, headers=('A','B'))

        message = DummyMessage('two')
        message['Date'] = 'Wed, 13 May 2010 02:42:15'
        message['A'] = 'foo'
        message['B'] = 'baz'
        queue.collect_frequency_data(message, headers=('A', 'B'))

        self.assertAlmostEqual(fut('Harry', now), 4.0)
        self.assertAlmostEqual(fut('Harry', now,
                                   headers={'A': 'foo', 'B': 'baz'}), 4.0)
        self.assertAlmostEqual(fut('Harry', now,
                                   headers={'A': 'foo', 'B': 'bar'}), 2.0)
        self.assertAlmostEqual(fut('Harry', now, {'A': 'mickey'}), 0.0)

    def test_get_average_frequency(self):
        from datetime import datetime
        from datetime import timedelta
        now = datetime(2010, 5, 12, 2, 43)
        interval = timedelta(minutes=1)
        queue = self._make_one()
        fut = queue.get_average_frequency
        self.assertAlmostEqual(fut('Harry', now, interval), 0.0)
        queue.collect_frequency_data(DummyMessage('one'))
        self.assertAlmostEqual(fut('Harry', now, interval), 1.0)
        queue.collect_frequency_data(DummyMessage('two'))
        self._set_now(now)
        now += timedelta(minutes=1)
        interval = timedelta(minutes=2)
        queue.collect_frequency_data(DummyMessage('three'))
        queue.collect_frequency_data(DummyMessage('four'))
        self.assertAlmostEqual(fut('Harry', now, interval), 2.0)
        now += timedelta(minutes=1)
        self.assertAlmostEqual(fut('Harry', now, interval), 1.0)
        now += timedelta(minutes=1)
        self.assertAlmostEqual(fut('Harry', now, interval), 0.0)

    def test_throttle(self):
        from datetime import datetime
        from datetime import timedelta
        queue = self._make_one()
        user = 'Harry'
        now = datetime(2010, 5, 12, 2, 42)
        self.failIf(queue.is_throttled(user, now))
        queue.throttle(user, now + timedelta(minutes=5))
        self.failUnless(queue.is_throttled(user, now))
        now += timedelta(minutes=6)
        self.failIf(queue.is_throttled(user, now))
        now += timedelta(minutes=6)
        self.failIf(queue.is_throttled(user, now))

    def test_throttle_with_headers(self):
        from datetime import datetime
        from datetime import timedelta
        queue = self._make_one()
        user = 'Harry'
        now = datetime(2010, 5, 12, 2, 42)
        headers = dict(A='foo', B='bar')
        self.failIf(queue.is_throttled(user, now, headers))
        queue.throttle(user, now + timedelta(minutes=5), headers)
        self.failUnless(queue.is_throttled(user, now, headers))
        self.failIf(queue.is_throttled(user, now))
        now += timedelta(minutes=6)
        self.failIf(queue.is_throttled(user, now, headers))
        now += timedelta(minutes=6)
        self.failIf(queue.is_throttled(user, now, headers))

class TestQueuedMessage(unittest.TestCase):
    def test_it(self):
        from repoze.postoffice.queue import _QueuedMessage
        message = DummyMessage('foobar')
        queued = _QueuedMessage(message)
        self.assertEqual(queued.get(), message)
        queued._v_message = None
        self.assertEqual(queued.get().get_payload(), 'foobar')

class Test_open_queue(unittest.TestCase):
    def _monkey_patch(self, queues):
        from repoze.postoffice import queue as module
        self.db = DummyDB({}, queues)
        module.db_from_uri = self.db

    def _call_fut(self, name):
        from repoze.postoffice.queue import open_queue
        return open_queue('dummy_uri', name)

    def test_it(self):
        q = 'one'
        self._monkey_patch(dict(one=q))
        self.assertEqual(self._call_fut('one')[0], q)
        self.failUnless(self.db.closed)

    def test_closer(self):
        q = 'one'
        self._monkey_patch(dict(one=q))
        queue, closer = self._call_fut('one')
        self.assertEqual(queue, q)
        self.failIf(self.db.closed)
        closer()
        self.failUnless(self.db.closed)

    def test_close_on_key_error(self):
        q = 'one'
        self._monkey_patch(dict(one=q))
        self.assertRaises(KeyError, self._call_fut, 'two')
        self.failUnless(self.db.closed)

from repoze.postoffice.message import Message
class DummyMessage(Message):
    def __init__(self, body=None):
        Message.__init__(self)
        self['From'] = 'Harry'
        self['Message-Id'] = '12345'
        self.set_payload(body)

    def __eq__(self, other):
        return self.get_payload().__eq__(other)

class DummyDB(object):
    def __init__(self, dbroot, queues):
        self.dbroot = dbroot
        self.queues = queues
        dbroot['postoffice'] = queues
        self.closed = False

    def __call__(self, uri):
        assert uri == 'dummy_uri'
        return self

    def open(self):
        return self

    def root(self):
        return self.dbroot

    def close(self):
        self.closed = True

from datetime import datetime
class DummyDatetime(object):
    _now = datetime(2010, 5, 12, 2, 42)

    def __call__(self, *args, **kw):
        return datetime(*args, **kw)

    @property
    def datetime(self):
        return self

    def now(self):
        return self._now
