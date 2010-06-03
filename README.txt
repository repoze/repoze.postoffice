=================
repoze.postoffice
=================

`repoze.postoffice` provides a centralized depot for collecting incoming email
for consumption by multiple applications.  Incoming mail is sorted into queues
according to rules with the expectation that each application will then consume
its own queue.  Each queue is a first-in-first-out (FIFO) queue, so messages
are processed in the order received.

ZODB is used for storage and is also used to provide the client interface.
`repoze.postoffice` clients create a ZODB connection and manipulate models.
This makes consuming the message queue in the context of a transaction,
relatively simple.

Setting up the depot
====================

`repoze.postoffice` assumes that a message transport agent (MTA), such as
Postfix, has been configured to deliver messages to a folder using the Maildir
format. Configuring the MTA is outside of the scope of this document.

The depot is configured via a configuration file in ini format.  The ini file
consists of a single 'post office' section followed by one or more named
queue sections.  The 'post office' section contains information about the ZODB
set up as well as the location of the incoming Maildir::

  [post office]
  # Required parameters
  zodb_uri = zconfig://%(here)s/zodb.conf#main
  maildir = %(here)s/incoming/Maildir

  # Optional parameters
  zodb_path = /postoffice
  ooo_loop_frequency = 60 # 1 Hertz
  ooo_throttle_period = 300 # 5 minutes
  max_message_size = 500m

`zodb_uri` is interpreted using `repoze.zodbconn` and follows the format laid
out there.  See: http://docs.repoze.org/zodbconn/narr.html

`zodb_path` is the path in the db to the postoffice queues.  This parameter
is optional and defaults to '/postoffice'.

`maildir` is the path to the incoming Maildir format folder from which messages
are pulled.

`ooo_loop_frequency` specifies the threshold frequency of incoming messages
from the same user to the same queue, in messages per minute. When the
threshold is reached by a particular user, messages from that user will be
discarded for period of time in an attempt to break a possible out of office
auto-reply loop. If not specified, no check is performed on frequency of
incoming messages.

`ooo_throttle_period` specifies the amount of time, in minutes, for which a
user's incoming mail will be discarded if a loop detection is in use and the
user reaches the `ooo_loop_frequency` threshold.  Defaults to 5 minutes.  If
`ooo_loop_frequency` is not set, this setting has no effect.

`max_message_size` sets the maximum size, in bytes, of incoming messages.
Messages which exceed this limit will be discarded. The sender will not be
informed. (This might be a later feature.) The suffixes 'k', 'm' or 'g' may be
used to specify that the number of bytes is expressed in kilobytes, megabytes
or gigabytes, respectively. A number without suffix will be interpreted as
bytes. If not set, no limit will be imposed on incoming message size.

Each message queue is configured in a section with the prefix 'queue:'::

  [queue:Customer A]
  filters =
      to_hostname: app.customera.com

  [queue:Customer B]
  filters =
      to_hostname: .customerb.com

Filters are used to determine which messages land in which queues. When a new
message enters the system each queue is tried in the order specified in the
ini file until a match is found or until all of the queues have been tried.
For each queue each filter for that queue is processed. In order to match for
a queue a message must match all filters for that queue.

At the time of this writing only a single filter is implemented: `to_hostname`.
This filter matches the hostname of the email address in the 'To' header of the
message.  Hostnames which beging with a period will match any hostname that
ends with the specified name, ie '.example.com' matches 'example.com' and
'app.example.com'.  If the hostname does not begin with a period it must
match exactly.

Populating Queues
=================

Queues are populated using the `postoffice` console script that is provided
when the `repoze.postoffice` egg is installed.  This script reads messages from
the incoming maildir and imports them into the ZODB-based depot.  Messages are
matched and placed in appropriate queues.  Messages which do not match any
queues are erased.  There are no required arguments to the script--if it can
find it's .ini file, it will work:

  $ bin/postoffice

The `postoffice` script will search for an ini file named 'postoffice.ini'
first in the current directory, then in an 'etc' folder in the current
directory, then an 'etc' folder that is a sibling of the 'bin' folder which
contains the `postoffice` script and then, finally, in '/etc'.  You can also
use a non-standard location for the ini file by passing the path as an
argument to the script:

  $ bin/postoffice -C path/to/config.ini

Use the '-h' or '--help' switch to see all of the options available.

Out of Office Loop Detection
============================

`repoze.postoffice` does attempt to address out of office loops. An out of
office loop can occur when `repoze.postoffice` is used to populate content in
an application which generates an email to alert users of the new content.
Essentially, a poorly behaved email client will respond to the new content
alert email with an out of office reply which in turn causes more content to
be created and another alert email to be sent. Without some form of loop
detection, this can lead to a large amount of junk content being generated
very quickly.

When a new email enters the system, `repoze.postoffice` first checks for some
headers that could be set by well behaved MTA's to indicate automated responses
and discards messages which match these known heuristics.  First, the
non-standard, but widely supported, 'Precedence' header is checked and messages
with a precedence of 'bulk', 'junk', or 'list' are discarded.  Next
`repoze.postoffice` will check for the presence of the 'Auto-Submitted' header
which is described in rfc3834 and is standard, but not yet widely supported.
Messages containing this header are discarded.

Out of office messages sent by certain clients (Microsoft) will typically not
use either of the above standards to indicate an automated reply. As a last
line of defense, `repoze.postoffice` also tracks the frequency of incoming
mail by email address. When the number of messages arriving from the same user
surpasses a particular, assumedly inhuman, threshold, a temporary block is
placed on messages from that user, such that all messages from that user are
discarded for a certain period of time, hopefully breaking the auto reply
feedback loop.

Consuming Queues
================

Client applications consume message queues by establishing a connection to the
ZODB which houses the depot and interacting with queue and message objects.
`repoze.postoffice.queue` contains a helper method, `open_queue` which given
connection information can open the connection for you and return a Queue
instance::

  from my.example import process_message
  from my.example import validate_message
  from repoze.postoffice.queue import open_queue
  import sys
  import transaction

  ZODB_URI = zconfig://%(here)s/zodb.conf#main
  queue_name = 'my queue'
  queue = open_queue(ZODB_URI, queue_name, path='/postoffice')
  while queue:
      message = queue.pop_next()
      if not validate_message(message):
          queue.bounce(message, 'Message is invalid.')
      try:
          process_message(message)
          transaction.commit()
      except:
          transaction.abort()
          queue.quarantine(message, sys.exc_info())
          transaction.commit()




