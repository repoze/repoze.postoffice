from __future__ import with_statement

import re


class ToHostnameFilter(object):
    """
    Matches the hostname of the email address in the 'To:' header of an email
    message.
    """
    def __init__(self, expr):
        self.expr = expr

    def __call__(self, message):
        addrs = []
        for header in 'To', 'Cc':
            value = message.get(header)
            if not value:
                continue
            addrs.extend(value.split(','))

        for addr in addrs:
            lt = addr.find('<')
            if lt != -1:
                addr = addr[lt+1:addr.rindex('>')]
            if '@' not in addr:
                continue
            hostname = addr.split('@')[1].lower()

            for expr in self.expr.lower().split():
                if expr.startswith('.') and hostname.endswith(expr[1:]):
                    return 'to_hostname: %s matches %s' % (addr, expr)
                if hostname == expr:
                    return 'to_hostname: %s matches %s' % (addr, expr)

        return None


class HeaderRegexpFilter(object):
    """
    Matches a regular expression on the headers of an email message.
    """
    def __init__(self, *exprs):
        self.regexps = [(expr, re.compile(expr, re.IGNORECASE))
                        for expr in exprs]

    def __call__(self, message):
        for name in message.keys():
            header = '%s: %s' % (name, message.get(name))
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
        with open(path) as f:
            for line in f:
                expr = line.strip()
                regexps.append((expr, re.compile(expr, re.IGNORECASE)))


class BodyRegexpFilter(object):
    """
    Matches a regular expression on the body of an email message (any part).
    """
    def __init__(self, *exprs):
        self.regexps = [(expr, re.compile(expr, re.IGNORECASE))
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
                    charset = content_type.split('charset=')[1]
            else:
                charset = str(charset)

            try_charsets = filter(None, [charset, 'UTF-8', 'ISO-8859-1'])
            for charset in try_charsets:
                try:
                    body = body.decode(charset)
                    break
                except UnicodeError:
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
        with open(path) as f:
            for line in f:
                expr = line.strip()
                regexps.append((expr, re.compile(expr, re.IGNORECASE)))
