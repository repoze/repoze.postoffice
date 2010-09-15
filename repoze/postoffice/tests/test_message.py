import unittest

class TestMessage(unittest.TestCase):
    def _target_class(self):
        from repoze.postoffice.message import Message as target
        return target

    def _make_one(self):
        return self._target_class()()

    def test_unicode_headers_roundtrip(self):
        m1 = self._make_one()
        m1['To'] = u'Ren\xe8 <test@example.com>'

        from email.parser import Parser
        parse = Parser(self._target_class()).parsestr
        m2 = parse(m1.as_string())
        self.assertEqual(m1['To'], m2['To'])

    def test_dont_encode_address(self):
        m1 = self._make_one()
        m1['To'] = u'Ren\xe8 <test@example.com>'
        msg = m1.as_string()
        to_header = [l for l in msg.split('\n') if l.startswith('To:')][0]
        self.assertEqual(to_header[-18:], '<test@example.com>')

    def test_address_that_is_not_an_address(self):
        # Damn spambots
        m1 = self._make_one()
        m1['To'] = u'\u041c\u0430\u0433\u0430\u0437\u0438\u043d \u043f\u043b'
        self.assertEqual(
            m1['To'], u'\u041c\u0430\u0433\u0430\u0437\u0438\u043d \u043f\u043b'
        )

    def test_bare_address(self):
        m1 = self._make_one()
        m1['To'] = 'test@example.com'
        msg = m1.as_string()
        to_header = [l for l in msg.split('\n') if l.startswith('To:')][0]
        self.assertEqual(to_header, 'To: test@example.com')

    def test_hide_encoded_headers_beneath_api(self):
        addr = u'Ren\xe8 <test@example.com>, Chr\xecs <chris@example.com>'
        m1 = self._make_one()
        m1['To'] = addr

        from email.parser import Parser
        parse = Parser(self._target_class()).parsestr
        m2 = parse(m1.as_string())
        self.assertEqual(m1['To'], m2['To'])
        self.assertEqual(m1['To'], addr)
        self.assertEqual(m2['To'], addr)

    def test_header_not_set(self):
        m1 = self._make_one()
        self.assertEqual(m1['Date'], None)

    def test_set_header_to_none(self):
        # Merely confirms that stdlib's oddball behavior of ignoring the fact
        # that you set a header to None still works.  Bizarre, useless edge
        # case.
        addr = u'Ren\xe8 <test@example.com>'
        m1 = self._make_one()
        m1['To'] = addr
        self.assertEqual(m1['To'], addr)
        m1['To'] = None
        self.assertEqual(m1['To'], addr)

    def test_non_address_header(self):
        proverb = u"Non c'\xe9 realt\xe0, c'\xe8 solo superpollo!"
        m1 = self._make_one()
        m1['Subject'] = proverb

        from email.parser import Parser
        parse = Parser(self._target_class()).parsestr
        m2 = parse(m1.as_string())
        self.assertEqual(m1['Subject'], m2['Subject'])
        self.assertEqual(m2['Subject'], proverb)

    def test_unicode_header_not_encoded_with_rfc2047(self):
        from email.message import Message
        proverb = u"Non c'\xe9 realt\xe0, c'\xe8 solo superpollo!"
        m1 = self._make_one()
        Message.__setitem__(m1, 'From', proverb)
        self.assertEqual(m1['From'], proverb)

    def test_utf8_header_not_encoded_with_rfc2047(self):
        from email.message import Message
        proverb = "Non c'\xc3\xa9 realt\xc3\xa0, c'\xc3\xa8 solo superpollo!"
        m1 = self._make_one()
        Message.__setitem__(m1, 'From', proverb)
        self.assertEqual(m1['From'], proverb)

class TestMIMEMultipPart(TestMessage):
    def _target_class(self):
        from repoze.postoffice.message import MIMEMultipart as target
        return target

