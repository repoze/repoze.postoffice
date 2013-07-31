from __future__ import with_statement

import codecs
import re

from repoze.postoffice.message import decode_header

_STANDARD_TO_HEADERS = ('To', 'Cc', 'X-Original-To')

class ToHostnameFilter(object):
    """Test the hostname of the email address in the specified message headers.
    """
    def __init__(self, expr, headers=_STANDARD_TO_HEADERS):
        if ';' in expr:
            expr, attrs = expr.split(';', 1)
            for a_expr in attrs.split(';'):
                name, value = [x.strip() for x in a_expr.split('=')]
                if name == 'headers':
                    headers = [x.strip() for x in value.split(',')]
                else:
                    raise ValueError('Unknown config attribute: %s' % name)
        self.expr = expr
        self.domains = expr.lower().split()
        self.headers = headers

    def __call__(self, message):
        addrs = []
        for header in self.headers:
            value = message.get(header)
            if not value:
                continue
            addrs.extend(value.split(','))

        for addr in addrs:
            lt = addr.find('<')
            if lt != -1:
                gt = addr.rfind('>')
                if gt == -1:
                    gt = None
                addr = addr[lt+1:gt]
            if '@' not in addr:
                continue
            hostname = addr.split('@')[1].lower()

            for domain in self.domains:
                if domain.startswith('.') and hostname.endswith(domain[1:]):
                    return 'to_hostname: %s matches %s' % (addr, domain)
                if hostname == domain:
                    return 'to_hostname: %s matches %s' % (addr, domain)

        return None


class HeaderRegexpFilter(object):
    """
    Matches a regular expression on the headers of an email message.
    """
    def __init__(self, *exprs):
        self.regexps = [(expr, re.compile(expr))
                        for expr in exprs]

    def __call__(self, message):
        for name in message.keys():
            header = '%s: %s' % (name, decode_header(message.get(name)))
            for regexp, compiled in self.regexps:
                if compiled.match(header) is not None:
                    return 'header_regexp: headers match %s' % repr(regexp)
        return None


class HeaderRegexpFileFilter(HeaderRegexpFilter):
    """
    Same as HeaderRegexpFilter but loads regexps from a file.
    """
    def __init__(self, path):
        self.regexps = regexps = []
        with codecs.open(path, 'r', 'UTF-8') as f:
            for line in f:
                expr = line.rstrip('\n').rstrip('\r')
                regexps.append((expr, re.compile(expr)))


class BodyRegexpFilter(object):
    """
    Matches a regular expression on the body of an email message (any part).
    """
    def __init__(self, *exprs):
        self.regexps = [(expr, re.compile(expr, re.MULTILINE))
                        for expr in exprs]

    def __call__(self, message):
        for part in message.walk():
            if not part.get_content_type().startswith('text/'):
                continue

            # Get body for this message part as unicode
            body = part.get_payload(decode=True)
            charset = part.get_charset()
            if charset is None:
                content_type = part.get('Content-Type')
                if content_type is not None and 'charset=' in content_type:
                    double_slash = content_type.find('//')
                    if double_slash != -1:
                        content_type = content_type[:double_slash].strip()
                    for piece in content_type.split(';'):
                        piece = piece.strip()
                        if piece.startswith('charset='):
                            charset = piece[8:]
                            break
            else:
                charset = str(charset)

            try_charsets = filter(None, [charset, 'UTF-8', 'ISO-8859-1'])
            for charset in try_charsets:
                try:
                    body = body.decode(charset)
                    break
                except (LookupError, UnicodeError):
                    pass

            # See if we match
            for regexp, compiled in self.regexps:
                if compiled.search(body) is not None:
                    return 'body_regexp: body matches %s' % repr(regexp)

        return None

class BodyRegexpFileFilter(BodyRegexpFilter):
    """
    Same as BodyRegexpFilter but loads regexps from a file.
    """
    def __init__(self, path):
        self.regexps = regexps = []
        with codecs.open(path, 'r', 'UTF-8') as f:
            for line in f:
                expr = line.rstrip('\n').rstrip('\r')
                regexps.append((expr, re.compile(expr, re.MULTILINE)))
