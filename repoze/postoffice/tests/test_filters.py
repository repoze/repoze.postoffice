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
