from __future__ import with_statement

import unittest

class TestToHostnameFilter(unittest.TestCase):
    def _make_one(self, expr):
        from repoze.postoffice.filters import ToHostnameFilter
        return ToHostnameFilter(expr)

    def test_absolute(self):
        fut = self._make_one('example.com')
        msg = {}
        self.failIf(fut(msg))
        msg['To'] = 'chris@foo.com'
        self.failIf(fut(msg))
        msg['To'] = 'chris@foo.example.com'
        self.failIf(fut(msg))
        msg['To'] = 'chris@example.com'
        self.failUnless(fut(msg))
        msg['To'] = 'Chris <chris@example.com>'
        self.failUnless(fut(msg))

    def test_relative(self):
        fut = self._make_one('.example.com')
        msg = {}
        self.failIf(fut(msg))
        msg['To'] = 'chris@foo.com'
        self.failIf(fut(msg))
        msg['To'] = 'chris@foo.example.com'
        self.failUnless(fut(msg))
        msg['To'] = 'chris@example.com'
        self.failUnless(fut(msg))
        msg['To'] = 'Chris <chris@example.com>'
        self.failUnless(fut(msg))

    def test_case_insensitive(self):
        fut = self._make_one('example.com')
        msg = {}
        self.failIf(fut(msg))
        msg['To'] = 'chris@Example.com'
        self.failUnless(fut(msg))

    def test_not_an_address(self):
        fut = self._make_one('example.com')
        msg = {'To': 'undisclosed recipients;;'}
        self.failIf(fut(msg))

    def test_malformed_address(self):
        fut = self._make_one('example.com')
        msg = {'To': 'karin@example.com <>'}
        self.failIf(fut(msg))

    def test_multiple_hosts(self):
        fut = self._make_one('example1.com .example2.com example3.com')
        msg = {'To': 'chris@foo.example2.com'}
        self.failUnless(fut(msg))
        msg = {'To': 'chris@foo.example1.com'}
        self.failIf(fut(msg))
        msg = {'To': 'chris@example1.com'}
        self.failUnless(fut(msg))

    def test_multiple_addrs(self):
        fut = self._make_one('example.com')
        msg = {'To': 'Fred <fred@exemplar.com>, Barney <barney@example.com>'}
        self.failUnless(fut(msg))

    def test_match_cc(self):
        fut = self._make_one('example.com')
        msg = {'To': 'Fred <fred@exemplar.com>, Barney <barney@example.com>'}
        self.failUnless(fut(msg))

    def test_match_to_or_cc(self):
        fut = self._make_one('example.com')
        msg = {'To': 'Fred <fred@examplar.com>',
               'Cc': 'Barney <barney@example.com>'}
        self.failUnless(fut(msg))
        msg = {'To': 'Barney <barney@example.com>',
               'Cc': 'Fred <fred@examplar.com>'}
        self.failUnless(fut(msg))


class TestHeaderRegexpFilter(unittest.TestCase):

    def _make_one(self, *exprs):
        from repoze.postoffice.filters import HeaderRegexpFilter as cut
        return cut(*exprs)

    def test_matches(self):
        fut = self._make_one('Subject:.+Party Time')
        msg = {'Subject': "It's that time!  Party time!"}
        self.failUnless(fut(msg))

    def test_does_not_match(self):
        fut = self._make_one('Subject:.+Party Time')
        msg = {'Subject': "It's time for a party!"}
        self.failIf(fut(msg))


class TestHeaderRegexpFileFilter(unittest.TestCase):

    def setUp(self):
        import os
        import tempfile
        self.tmp = tempfile.mkdtemp('.repoze.postoffice.tests')
        self.path = os.path.join(self.tmp, 'rules')
        with open(self.path, 'w') as out:
            print >> out, "Subject:.+Party Time"
            print >> out, "From:.+ROSSI"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _make_one(self):
        from repoze.postoffice.filters import HeaderRegexpFileFilter as cut
        return cut(self.path)

    def test_matches(self):
        fut = self._make_one()
        msg = {'Subject': "It's that time!  Party time!"}
        self.failUnless(fut(msg))
        msg = {'From': 'chris.rossi@jackalopelane.net'}
        self.failUnless(fut(msg))

    def test_does_not_match(self):
        fut = self._make_one()
        msg = {'Subject': "It's time for a party!"}
        self.failIf(fut(msg))


class TestBodyRegexpFilter(unittest.TestCase):

    def _make_one(self, *exprs):
        from repoze.postoffice.filters import BodyRegexpFilter as cut
        return cut(*exprs)

    def test_matches(self):
        from email.message import Message
        msg = Message()
        msg.set_payload("I am full of happy babies.  All Days for Me!")
        fut = self._make_one('happy.+days')
        self.failUnless(fut(msg))

    def test_does_not_match(self):
        from email.message import Message
        msg = Message()
        msg.set_payload("All Days for Me!  I am full of happy babies.")
        fut = self._make_one('happy.+days')
        self.failIf(fut(msg))


class TestBodyRegexpFileFilter(unittest.TestCase):

    def setUp(self):
        import os
        import tempfile
        self.tmp = tempfile.mkdtemp('.repoze.postoffice.tests')
        self.path = os.path.join(self.tmp, 'rules')
        with open(self.path, 'w') as out:
            print >> out, "happy.+days"
            print >> out, "amnesia"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _make_one(self):
        from repoze.postoffice.filters import BodyRegexpFileFilter as cut
        return cut(self.path)

    def test_matches(self):
        from email.message import Message
        msg = Message()
        msg.set_payload("I am full of happy babies.  All Days for Me!")
        fut = self._make_one()
        self.failUnless(fut(msg))

    def test_matches_multipart(self):
        from email.mime.multipart import MIMEMultipart
        from email.mime.multipart import MIMEBase
        from email.mime.text import MIMEText
        msg = MIMEMultipart()
        body = MIMEText('I am full of happy babies.  All Days for Me!')
        msg.attach(body)
        other = MIMEBase('application', 'pdf')
        other.set_payload('Not really a pdf.')
        msg.attach(other)
        fut = self._make_one()
        self.failUnless(fut(msg))

        msg = MIMEMultipart()
        body = MIMEText("I can't remember if my amnesia is getting worse.")
        msg.attach(body)
        other = MIMEBase('application', 'pdf')
        other.set_payload('Not really a pdf.')
        msg.attach(other)
        self.failUnless(fut(msg))

    def test_does_not_match(self):
        from email.message import Message
        msg = Message()
        msg.set_payload("All Days for Me!  I am full of happy babies.")
        fut = self._make_one()
        self.failIf(fut(msg))

    def test_does_not_multipart(self):
        from email.mime.multipart import MIMEMultipart
        from email.mime.multipart import MIMEBase
        msg = MIMEMultipart()
        body = MIMEBase('x-application', 'not-text')
        body.set_payload('I am full of happy babies.  All Days for Me!')
        msg.attach(body)
        other = MIMEBase('application', 'pdf')
        other.set_payload('Not really a pdf.')
        msg.attach(other)
        fut = self._make_one()
        self.failIf(fut(msg))
