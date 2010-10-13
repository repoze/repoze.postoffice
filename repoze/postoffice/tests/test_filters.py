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
