import unittest

class TestQueue(unittest.TestCase):
    def _make_one(self):
        from repoze.postoffice.queue import Queue
        return Queue()

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
        queue.bounce(bounced, send, 'Bouncer <bouncer@example.com>',
                     bounce_message='TEST')

        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, message = send.sent[0]
        self.assertEqual(fromaddr, 'Bouncer <bouncer@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(message, 'TEST')

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
                     u'Not entertaining enough.')

        self.assertEqual(len(send.sent), 1)
        fromaddr, toaddrs, message = send.sent[0]
        self.assertEqual(fromaddr, 'Bouncer <bouncer@example.com>')
        self.assertEqual(message['From'], 'Bouncer <bouncer@example.com>')
        self.assertEqual(toaddrs, ['Chris Rossi <chris@example.com>'])
        self.assertEqual(message['To'], 'Chris Rossi <chris@example.com>')
        self.failUnless(message['Subject'].startswith(
            'Your message to Submissions'), message['Subject'])
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
        module.db_from_uri = DummyDB({}, queues)

    def _call_fut(self, name):
        from repoze.postoffice.queue import open_queue
        return open_queue('dummy_uri', name)

    def test_it(self):
        q = 'one'
        self._monkey_patch(dict(one=q))
        self.assertEqual(self._call_fut('one'), q)

from repoze.postoffice.message import Message
class DummyMessage(Message):
    def __init__(self, body=None):
        Message.__init__(self)
        self.set_payload(body)

    def __eq__(self, other):
        return self.get_payload().__eq__(other)

class DummyDB(object):
    def __init__(self, dbroot, queues):
        self.dbroot = dbroot
        self.queues = queues
        dbroot['postoffice'] = queues

    def __call__(self, uri):
        assert uri == 'dummy_uri'
        return self

    def open(self):
        return self

    def root(self):
        return self.dbroot
