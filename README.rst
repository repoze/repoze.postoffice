``repoze.postoffice`` README
============================

``repoze.postoffice`` provides a centralized depot for collecting incoming
email for consumption by multiple applications.  Incoming mail is sorted
into queues according to rules with the expectation that each application
will then consume its own queue.  Each queue is a first-in-first-out (FIFO)
queue, so messages are processed in the order received.

ZODB is used for storage and is also used to provide the client interface.
``repoze.postoffice`` clients create a ZODB connection and manipulate models.
This makes consuming the message queue in the context of a transaction,
relatively simple.

Please see ``docs/index.rst`` for the complete documentation.
