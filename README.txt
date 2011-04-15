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

Configuration File
++++++++++++++++++

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
    ooo_loop_headers = To,Subject
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
marked as rejected for period of time in an attempt to break a possible out
of office auto-reply loop. If not specified, no check is performed on
frequency of incoming messages.

`ooo_loop_headers` optionally causes loop detection to use the specified email
headers as discriminators.  If specified, these headers must match for incoming
messages to trigger the ooo throttle.  If not specified, no header matching is
done, and messages need only be sent from the same user to the same queue to
trigger the throttle.

`ooo_throttle_period` specifies the amount of time, in minutes, for which a
user's incoming mail will be marked as rejected if loop detection is in use
and the user reaches the `ooo_loop_frequency` threshold. Defaults to 5
minutes. If `ooo_loop_frequency` is not set, this setting has no effect.

`max_message_size` sets the maximum size, in bytes, of incoming messages.
Messages which exceed this limit will have their payloads discarded and will
be marked as rejected. The suffixes 'k', 'm' or 'g' may be used to specify
that the number of bytes is expressed in kilobytes, megabytes or gigabytes,
respectively. A number without suffix will be interpreted as bytes. If not
set, no limit will be imposed on incoming message size.

Each message queue is configured in a section with the prefix 'queue:'::

    [queue:Customer A]
    filters =
        to_hostname: app.customera.com app.aliasa.com

    [queue:Customer B]
    filters =
        to_hostname: .customerb.com

Filters
+++++++

Filters are used to determine which messages land in which queues. When a new
message enters the system each queue is tried in the order specified in the
ini file until a match is found or until all of the queues have been tried.
For each queue each filter for that queue is processed. In order to match for
a queue a message must match all filters for that queue.

At the time of the following filters are implemented:

+ `to_hostname`: This filter matches the hostname of the email address in the
  'To' or 'CC' headers of the message. Hostnames which beging with a period will
  match any hostname that ends with the specified name, ie '.example.com'
  matches 'example.com' and 'app.example.com'. If the hostname does not begin
  with a period it must match exactly. Multiple hostnames, delimited by
  whitespace, may be listed. If multiple hostnames are used, an incoming message
  need match only one.

+ `header_regexp`: This filter allows the matching of arbitrary regular
  expressions against the headers of a message.  Only a single regular
  expression can be specified.  An example::

    [queue:Parties]
    filters =
        header_regexp: Subject:.+[Pp]arty.+

+ `header_regexp_file`: This filter is the same as `header_regexp` except that
  multiple regular expressions can be written in a file. Regular expressions are
  newline delimited in the file. The argument to this filter is the path to the
  file::

    [queue:Weddings]
    filters =
        header_regexp_file: %(here)s/wedding_invitation_header_checks.txt

+ `body_regexp`: Like `header_regexp` except the regular expression must match
  some text in one of the message part bodies.

+ `body_regexp_file`: Like `header_regexp_file` except the regular expressions
  must match some text in one of the message part bodies.

Global Reject Filters
+++++++++++++++++++++

In addition to defining filters for queues, filters can be defined globally
for rejection of messages before they can be assigned to queues. Any filter
that can be used for a queue can be used here. The basic difference, though,
is that for a queue, if a filter matches, the message goes into the queue.
Here, though, if a filter matches the message is rejected.  ::

    [post office]
    reject_filters =
        header_regexp_file: reject_headers.txt
        body_regexp_file: reject_body.txt
        to_hostname: *.partycentral.com  # We need to get them to change their MX

Populating Queues
=================

Queues are populated using the `postoffice` console script that is provided
when the `repoze.postoffice` egg is installed.  This script reads messages from
the incoming maildir and imports them into the ZODB-based depot.  Messages are
matched and placed in appropriate queues.  Messages which do not match any
queues are erased.  There are no required arguments to the script--if it can
find its .ini file, it will work::

    $ bin/postoffice

The `postoffice` script will search for an ini file named 'postoffice.ini'
first in the current directory, then in an 'etc' folder in the current
directory, then an 'etc' folder that is a sibling of the 'bin' folder which
contains the `postoffice` script and then, finally, in '/etc'.  You can also
use a non-standard location for the ini file by passing the path as an
argument to the script::

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
headers that could be set by well behaved MTA's to indicate automated
responses and marks as rejected messages which match these known heuristics.
First, the non-standard, but widely supported, 'Precedence' header is checked
and messages with a precedence of 'bulk', 'junk', or 'list' are marked as
rejected. Next `repoze.postoffice` will check for the presence of the
'Auto-Submitted' header which is described in rfc3834 and is standard, but not
yet widely supported. Messages containing this header are marked. In either of
these two cases, the incoming message is marked by adding the header::

  X-Postoffice-Rejected: Auto-response

Out of office messages sent by certain clients (Microsoft) will typically not
use either of the above standards to indicate an automated reply. As a last
line of defense, `repoze.postoffice` also tracks the frequency of incoming
mail by email address and, optionally, other headers specified by the
'ooo_loop_headers' configuration option. When the number of messages arriving
from the same user surpasses a particular, assumedly inhuman, threshold, a
temporary block is placed on messages from that user, such that all messages
from that user are marked as rejected for a certain period of time, hopefully
breaking the auto reply feedback loop. Messages which trigger are fall under a
throttle are marked with header::

  X-Postoffice-Rejected: Throttled

Messages marked with the 'X-Postoffice-Rejected' header are still conveyed to
the client.  It is up to the client to check for this header and take
appropriate action.  This allows the client to choose and take appropriate
action, such as bouncing with a particular bounce message, etc.

Message Size Limit
==================

If 'max_message_size' is specified in the configuration, messages which exceed
this size will have their payloads (body and any attachments) discarded and
will be marked with the header:

  X-Postoffice-Rejected: Maximum Message Size Exceeded

The trimmed message is still conveyed to the client, which should check for
the 'X-Postoffice-Rejected' header and take appropriate action, possibly
including bouncing the message with an appropriate bounce message.

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
