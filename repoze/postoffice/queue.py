from BTrees.IOBTree import IOBTree
from BTrees.OOBTree import OOBTree
from persistent import Persistent
from persistent.list import PersistentList
from ZODB.blob import Blob

import email.generator
import email.message
import email.parser
from email.utils import parsedate

from repoze.postoffice.message import Message
from repoze.zodbconn.uri import db_from_uri

import datetime
import time

def open_queue(zodb_uri, queue_name, path='postoffice'):
    db = db_from_uri(zodb_uri)
    conn = db.open()
    queues = conn.root()
    for name in path.strip('/').split('/'):
        queues = queues[name]
    return queues[queue_name], _Closer(db, conn)

class _Closer(object):
    def __init__(self, db, conn):
        self.closed = False
        self.db = db
        self.conn = conn

    def __call__(self):
        self.__del__()

    def __del__(self):
        if not self.closed:
            self.conn.close()
            del self.conn
            self.db.close()
            del self.db
            self.closed = True

class QueuesFolder(OOBTree):
    """
    Container for post office queues.
    """

class Queue(Persistent):
    """
    Implements a first in first out (FIFO) message queue.
    """
    def __init__(self):
        self._quarantine = IOBTree()
        self._messages = IOBTree()
        self._freq_data = OOBTree()

    def add(self, message):
        """
        Add a message to the queue.
        """
        user = message['From']
        date = message.get('Date')
        message = _QueuedMessage(message)
        id = _new_id(self._messages)
        self._messages[id] = message

        # Save frequency data
        if date is not None:
            date = datetime.datetime(*parsedate(date)[:6])
        else:
            date = datetime.datetime.now()
        times = self._freq_data.get(user)
        if times is None:
            times = _FreqData()
            self._freq_data[user] = times
        times.append(date)

    def pop_next(self):
        """
        Retrieve the next message in the queue, removing it from the queue.
        """
        key = iter(self._messages.keys()).next()
        message = self._messages.pop(key)
        return message.get()

    def __len__(self):
        return self._messages.__len__()

    def bounce(self, message, send,
               bounce_from_addr,
               bounce_reason=None,
               bounce_message=None):
        """
        Sends a bounce message to the sender of 'message'. The mechanism for
        mail delivery is passed in via the 'send' argument. 'bounce_from_addr'
        specifices the email address the bounce message should be from. If
        'bounce_reason' is specified, a bounce message will be generated using
        the given bounce reason, a string. If 'bounce_message' is specified,
        the given bounce message is sent, rather than generating a new one.
        'bounce_message' should be an instance of `email.message.Message`.
        If neither 'bounce_reason' or 'bounce_message' is specified, a generic
        bounce message will be sent.  Specifying both is an error.

        The 'send' argument is a callable with the following signature::

            def send(fromaddr, toaddrs, message):
                 "Send an email message."

        Implementations can be found in `repoze.sendmail`.  See
        `repoze.sendmail.delivery.QueuedMailDelivery.send` or
        `repoze.sendmail.delivery.DirectMailDelivery.send`.
        """
        if bounce_reason is not None and bounce_message is not None:
            raise ValueError(
                "May only specify one of either 'bounce_reason' or "
                "'bounce_message'."
            )

        toaddrs = [message['From'],]
        if bounce_message is None:
            if bounce_reason is None:
                bounce_reason = 'Email message is invalid.'
            elif isinstance(bounce_reason, unicode):
                bounce_reason = bounce_reason.encode('UTF-8')
            if 'Date' in message:
                date = message['Date']
            else:
                date = datetime.datetime.now().ctime()
            bounce_to = message['To']
            subject = 'Your message to %s has bounced.' % bounce_to
            bounce_message = Message()
            bounce_message['Subject'] = subject
            bounce_message['From'] = bounce_from_addr
            bounce_message['To'] = message['From']
            bounce_message.set_payload(_default_bounce_body %
                                (date, bounce_to, bounce_reason), 'UTF-8'
                                )
        send(bounce_from_addr, toaddrs, bounce_message)

    def quarantine(self, message, error, send=None, notice_from=None):
        """
        Adds a message and corresponding exception info to the 'quarantine'.
        If an application attempts to process a message and encounters an
        exception it may choose to place the message in quarantine such that
        the message and corresponding exception info can be examined by
        developers and/or site administrators.  Once the problem causing the
        exception has been addressed, the messages can be requeued and tried
        again.

        The 'send' argument is optional. If specified it will be used to notify
        the sender of the message that their message has been quarantined. The
        'send' argument is a callable with the following signature::

            def send(fromaddr, toaddrs, message):
                 "Send an email message."

        Implementations can be found in `repoze.sendmail`.  See
        `repoze.sendmail.delivery.QueuedMailDelivery.send` or
        `repoze.sendmail.delivery.DirectMailDelivery.send`.

        If 'send' is specificed, 'notice_from' must also be specified, where
        'notice_from' is the apparent from email address of the notice sent to
        the sender.
        """
        if send is not None and notice_from is None:
            raise ValueError("Must specify 'notice_from' in order to send "
                             "notice.")

        quarantine = self._quarantine
        id = _new_id(quarantine)
        message['X-Postoffice-Id'] = str(id)
        quarantine[id] = (_QueuedMessage(message), error)

        if send is not None:
            notice = Message()
            notice['Subject'] = ('An error has occurred while processing your '
                                 'email to %s' % message['To'])
            notice['From'] = notice_from
            notice['To'] = message['From']
            if 'Date' in message:
                date = message['Date']
            else:
                date = datetime.datetime.now().ctime()
            notice.set_payload(_quarantine_notice_body % (date, message['To']),
                               'UTF-8')
            send(notice_from, [message['From'],], notice)

    def get_quarantined_messages(self):
        """
        Returns an iterator over the messages currently in the quarantine.
        """
        for message, error in self._quarantine.values():
            yield message.get(), error

    def get_quarantined_message(self, id):
        id = int(id)
        return self._quarantine[id][0].get()

    def count_quarantined_messages(self):
        """
        Returns the number of messages in the quarantine.
        """
        return len(self._quarantine)

    def remove_from_quarantine(self, message):
        """
        Removes the given message from the quarantine.
        """
        id = message.get('X-Postoffice-Id')
        if id is None:
            raise ValueError("Message is not in the quarantine.")
        id = int(id)
        if id not in self._quarantine:
            raise ValueError("Message is not in the quarantine.")
        del self._quarantine[id]
        del message['X-Postoffice-Id']

    def get_instantaneous_frequency(self, user, now):
        """
        Gets the instantaneous frequency of message submission for the given
        user. The frequency is a floating point number representing messages
        per minute. The instantaneous frequency is calculated using the time
        interval between now and the time of the user's last submitted
        message. The 'user' argument matches the 'From' field of the incoming
        messages.  If no data is available about user's last submitted message,
        the frequency will be 0.0.
        """
        freq_data = self._freq_data.get(user)
        if not freq_data:
            return 0.0
        delta = now - freq_data[-1]
        return 60.0 / _timedelta_as_seconds(delta)

    def get_average_frequency(self, user, now, interval):
        """
        Gets the average frequency of message submission for the given user
        over the given time interval. The frequency is a floating point number
        representing messages per minute. The average frequency is calculated
        by looking at the number of messages received from the user from now -
        interval until now. The 'user' argument matches the 'From' field of
        the incoming messages. The interval argument should be an instance of
        `datetime.timedelta`. Frequency data for messages received prior to
        the interval of interest will be deleted.
        """
        freq_data = self._freq_data.get(user)
        start = now - interval
        while freq_data and freq_data[0] < start:
            del freq_data[0]
        if not freq_data:
            return 0.0
        count = 0
        for timestamp in freq_data:
            if timestamp < now:
                count += 1
        return 60.0 * count / _timedelta_as_seconds(interval)

class _QueuedMessage(Persistent):
    """
    Wrapper for storing email messages in queues.  Stores email as flattened
    bytes in a blob.
    """
    _v_message = None  # memcache message once loaded

    def __init__(self, message):
        assert isinstance(message, email.message.Message), "Not a message."
        self._v_message = message   # transient attribute
        self._blob_file = blob = Blob()
        outfp = blob.open('w')
        email.generator.Generator(outfp).flatten(message)
        outfp.close()

    def get(self):
        if self._v_message is None:
            parser = email.parser.Parser(Message)
            self._v_message = parser.parse(self._blob_file.open())
        return self._v_message

class _FreqData(PersistentList):
    throttled = False

def _new_id(container):
    # Use numeric incrementally increasing ids to preserve FIFO order
    if len(container):
        return max(container.keys()) + 1
    return 0

def _timedelta_as_seconds(td):
    return (24.0 * 60.0 * 60.0 * td.days +
            td.seconds +
            td.microseconds / 1000000)

_default_bounce_body = """
Your email, sent on %s to %s has bounced for the following reason:

\t%s

If you feel you are receiving this message in error please contact your system
administrator.
""".lstrip()

_quarantine_notice_body = """
An error has occurred while processing your email, sent on %s to %s.

System administrators have been informed and will take corrective action
shortly. Your message has been stored in a quarantine and will be retried once
the error is addressed. We apologize for the inconvenience.
""".lstrip()
