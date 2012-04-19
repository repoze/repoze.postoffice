from __future__ import with_statement

import unittest

class TestToHostnameFilter(unittest.TestCase):
    def _make_one(self, expr):
        from repoze.postoffice.filters import ToHostnameFilter
        return ToHostnameFilter(expr)

    def test_absolute(self):
        fut = self._make_one('example.com')
        msg = {}
        self.assertEqual(fut(msg), None)
        msg['To'] = 'chris@foo.com'
        self.assertEqual(fut(msg), None)
        msg['To'] = 'chris@foo.example.com'
        self.assertEqual(fut(msg), None)
        msg['To'] = 'chris@example.com'
        self.assertEqual(fut(msg),
                         'to_hostname: chris@example.com matches example.com')
        msg['To'] = 'Chris <chris@example.com>'
        self.assertEqual(fut(msg),
                         'to_hostname: chris@example.com matches example.com')

    def test_relative(self):
        fut = self._make_one('.example.com')
        msg = {}
        self.assertEqual(fut(msg), None)
        msg['To'] = 'chris@foo.com'
        self.assertEqual(fut(msg), None)
        msg['To'] = 'chris@foo.example.com'
        self.assertEqual(fut(msg),
                    'to_hostname: chris@foo.example.com matches .example.com')
        msg['To'] = 'chris@example.com'
        self.assertEqual(fut(msg),
                    'to_hostname: chris@example.com matches .example.com')
        msg['To'] = 'Chris <chris@example.com>'
        self.assertEqual(fut(msg),
                         'to_hostname: chris@example.com matches .example.com')


    def test_case_insensitive(self):
        fut = self._make_one('example.com')
        msg = {}
        self.assertEqual(fut(msg), None)
        msg['To'] = 'chris@Example.com'
        self.assertEqual(fut(msg),
                         'to_hostname: chris@Example.com matches example.com')


    def test_not_an_address(self):
        fut = self._make_one('example.com')
        msg = {'To': 'undisclosed recipients;;'}
        self.assertEqual(fut(msg), None)

    def test_malformed_address(self):
        fut = self._make_one('example.com')
        msg = {'To': 'karin@example.com <>'}
        self.assertEqual(fut(msg), None)

    def test_multiple_hosts(self):
        fut = self._make_one('example1.com .example2.com example3.com')
        msg = {'To': 'chris@foo.example2.com'}
        self.assertEqual(fut(msg),
            'to_hostname: chris@foo.example2.com matches .example2.com')
        msg = {'To': 'chris@foo.example1.com'}
        self.assertEqual(fut(msg), None)
        msg = {'To': 'chris@example1.com'}
        self.assertEqual(fut(msg),
            'to_hostname: chris@example1.com matches example1.com')

    def test_multiple_addrs(self):
        fut = self._make_one('example.com')
        msg = {'To': 'Fred <fred@exemplar.com>, Barney <barney@example.com>'}
        self.assertEqual(fut(msg),
                         'to_hostname: barney@example.com matches example.com')

    def test_match_cc(self):
        fut = self._make_one('example.com')
        msg = {'Cc': 'Fred <fred@exemplar.com>, Barney <barney@example.com>'}
        self.assertEqual(fut(msg),
                         'to_hostname: barney@example.com matches example.com')

    def test_match_to_or_cc(self):
        fut = self._make_one('example.com')
        msg = {'To': 'Fred <fred@examplar.com>',
               'Cc': 'Barney <barney@example.com>'}
        self.assertEqual(fut(msg),
                         'to_hostname: barney@example.com matches example.com')
        msg = {'To': 'Barney <barney@example.com>',
               'Cc': 'Fred <fred@examplar.com>'}
        self.assertEqual(fut(msg),
                         'to_hostname: barney@example.com matches example.com')


class TestHeaderRegexpFilter(unittest.TestCase):

    def _make_one(self, *exprs):
        from repoze.postoffice.filters import HeaderRegexpFilter as cut
        return cut(*exprs)

    def test_matches(self):
        regexp = 'Subject:.+Party Time'
        fut = self._make_one(regexp)
        msg = {'Subject': "It's that time!  Party time!"}
        self.assertEqual(fut(msg),
                         'header_regexp: headers match %s' % repr(regexp))

    def test_does_not_match(self):
        fut = self._make_one('Subject:.+Party Time')
        msg = {'Subject': "It's time for a party!"}
        self.assertEqual(fut(msg), None)

    def test_matches_non_ascii(self):
        regexp = u'Subject: .*R\xe9ponse automatique\xa0'
        fut = self._make_one(regexp)
        msg = {'Subject': '=?iso-8859-1?Q?R=E9ponse_automatique=A0:_'
               '[Communications_&_PR]_Civil_soci?='}
        self.assertEqual(fut(msg),
                         'header_regexp: headers match %s' % repr(regexp))


class TestHeaderRegexpFileFilter(unittest.TestCase):

    def setUp(self):
        import os
        import tempfile
        self.tmp = tempfile.mkdtemp('.repoze.postoffice.tests')
        self.path = os.path.join(self.tmp, 'rules')
        with open(self.path, 'w') as out:
            print >> out, "Subject:.+Party Time"
            print >> out, "Subject:.+pecial "
            print >> out, "From:.+ROSSI"
            print >> out, 'Subject: .*R\xc3\xa9ponse automatique\xc2\xa0'

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _make_one(self):
        from repoze.postoffice.filters import HeaderRegexpFileFilter as cut
        return cut(self.path)

    def test_matches(self):
        fut = self._make_one()
        msg = {'Subject': "It's that time!  Party time!"}
        self.assertEqual(fut(msg),
                         "header_regexp: headers match u'Subject:.+Party Time'")
        msg = {'From': 'chris.rossi@jackalopelane.net'}
        self.assertEqual(fut(msg),
                         "header_regexp: headers match u'From:.+ROSSI'")

    def test_respect_trailing_whitespace(self):
        fut = self._make_one()
        msg = {'Subject': "Call a specialist."}
        self.assertEqual(fut(msg), None)
        msg = {'Subject': 'Hmm, hmm, yummy pecial for you.'}
        self.assertEqual(fut(msg),
                         "header_regexp: headers match u'Subject:.+pecial '")

    def test_does_not_match(self):
        fut = self._make_one()
        msg = {'Subject': "It's time for a party!"}
        self.assertEqual(fut(msg), None)

    def test_matches_non_ascii(self):
        fut = self._make_one()
        msg = {'Subject': '=?iso-8859-1?Q?R=E9ponse_automatique=A0:_'
               '[Communications_&_PR]_Civil_soci?='}
        self.assertEqual(fut(msg),
                         "header_regexp: headers match "
                         "u'Subject: .*R\\xe9ponse automatique\\xa0'")


class TestBodyRegexpFilter(unittest.TestCase):

    def _make_one(self, *exprs):
        from repoze.postoffice.filters import BodyRegexpFilter as cut
        return cut(*exprs)

    def test_matches(self):
        from email.message import Message
        msg = Message()
        msg.set_payload("I am full of happy babies.  All Days for Me!")
        fut = self._make_one('happy.+days')
        self.assertEqual(fut(msg),
                         "body_regexp: body matches 'happy.+days'")

    def test_does_not_match(self):
        from email.message import Message
        msg = Message()
        msg.set_payload("All Days for Me!  I am full of happy babies.")
        fut = self._make_one('happy.+days')
        self.assertEqual(fut(msg), None)

    def test_multiline_matches(self):
        from email.message import Message
        msg = Message()
        # we've seen messages with From/Subject looking headers in the body
        msg.set_payload("From: foobar@example.com\nSubject: Auto-Response")
        fut = self._make_one('^Subject: Auto-Response')
        self.assertEqual(fut(msg),
                         "body_regexp: body matches '^Subject: Auto-Response'")


class TestBodyRegexpFileFilter(unittest.TestCase):

    def setUp(self):
        import os
        import tempfile
        self.tmp = tempfile.mkdtemp('.repoze.postoffice.tests')
        self.path = os.path.join(self.tmp, 'rules')
        with open(self.path, 'w') as out:
            print >> out, "happy.+days"
            print >> out, "amnesia"
            print >> out, " (kitties|corndogs|puppies) "

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
        self.assertEqual(fut(msg),
                         "body_regexp: body matches u'happy.+days'")

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
        self.assertEqual(fut(msg),
                         "body_regexp: body matches u'happy.+days'")

        msg = MIMEMultipart()
        body = MIMEText("I can't remember if my amnesia is getting worse.")
        msg.attach(body)
        other = MIMEBase('application', 'pdf')
        other.set_payload('Not really a pdf.')
        msg.attach(other)
        self.assertEqual(fut(msg),
                         "body_regexp: body matches u'amnesia'")

    def test_does_not_match(self):
        from email.message import Message
        msg = Message()
        msg.set_payload("All Days for Me!  I am full of happy babies.")
        fut = self._make_one()
        self.assertEqual(fut(msg), None)

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
        self.assertEqual(fut(msg), None)

    def test_matches_multipart_w_charset_in_content_type(self):
        """
        Simulates mime messages created by stdlib email parser where  a part
        can have a charset set in the Content-Type header but get_charset()
        returns None.
        """
        from email.mime.multipart import MIMEMultipart
        from email.mime.multipart import MIMEBase
        from email.mime.text import MIMEText
        msg = MIMEMultipart()
        body = MIMEText('I am full of happy babies.  All Days for Me!')
        body.set_charset(None)
        del body['Content-Type']
        body['Content-Type'] = 'text/plain; charset=ISO-8859-1; flow=groovy'
        msg.attach(body)
        other = MIMEBase('application', 'pdf')
        other.set_payload('Not really a pdf.')
        msg.attach(other)
        fut = self._make_one()
        self.assertEqual(fut(msg),
                         "body_regexp: body matches u'happy.+days'")

    def test_matches_multipart_w_bogus_charset_in_content_type(self):
        """
        Simulates mime messages created by stdlib email parser where  a part
        can have a charset set in the Content-Type header but get_charset()
        returns None.
        """
        from email.mime.multipart import MIMEMultipart
        from email.mime.multipart import MIMEBase
        from email.mime.text import MIMEText
        msg = MIMEMultipart()
        body = MIMEText('I am full of happy babies.  All Days for Me!')
        body.set_charset(None)
        del body['Content-Type']
        body['Content-Type'] = 'text/plain; charset=bogus; flow=groovy'
        msg.attach(body)
        other = MIMEBase('application', 'pdf')
        other.set_payload('Not really a pdf.')
        msg.attach(other)
        fut = self._make_one()
        self.assertEqual(fut(msg),
                         "body_regexp: body matches u'happy.+days'")

    def test_matches_multipart_w_comment_in_charset(self):
        """
        At least one email client out there generates content type headers that
        look like::

            Content-Type: text/html; charset="utf-8" //iso-8859-2
        """
        from email.mime.multipart import MIMEMultipart
        from email.mime.multipart import MIMEBase
        from email.mime.text import MIMEText
        msg = MIMEMultipart()
        body = MIMEText('I am full of happy babies.  All Days for Me!')
        body.set_charset(None)
        del body['Content-Type']
        body['Content-Type'] = 'text/plain; charset="utf-8" //iso-8859-2'
        msg.attach(body)
        other = MIMEBase('application', 'pdf')
        other.set_payload('Not really a pdf.')
        msg.attach(other)
        fut = self._make_one()
        self.assertEqual(fut(msg),
                         "body_regexp: body matches u'happy.+days'")

    def test_does_not_match_multipart_w_no_charset_not_utf8(self):
        """
        Simulates mime messages created by stdlib email parser where  a part
        can have a charset set in the Content-Type header but get_charset()
        returns None.
        """
        from email.mime.multipart import MIMEMultipart
        from email.mime.multipart import MIMEBase
        from email.mime.text import MIMEText
        body_text = u'Non \xe8 giusto costringermi ad usare il modulo email.'
        msg = MIMEMultipart()
        body = MIMEText(body_text.encode('ISO-8859-1'))
        body.set_charset(None)
        msg.attach(body)
        other = MIMEBase('application', 'pdf')
        other.set_payload('Not really a pdf.')
        msg.attach(other)
        fut = self._make_one()
        self.assertEqual(fut(msg), None)

    def test_respects_leading_and_trailing_whitespace(self):
        from email.message import Message
        msg = Message()
        msg.set_payload("You are such scorndogs.")
        fut = self._make_one()
        self.assertEqual(fut(msg), None)
        msg.set_payload("Have puppies for lunch!")
        self.assertEqual(fut(msg),
                "body_regexp: body matches u' (kitties|corndogs|puppies) '")
