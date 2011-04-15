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
            addr = addr.lower()
            lt = addr.find('<')
            if lt != -1:
                addr = addr[lt+1:addr.rindex('>')]
            if '@' not in addr:
                continue
            hostname = addr.split('@')[1]

            for expr in self.expr.lower().split():
                if expr.startswith('.') and hostname.endswith(expr[1:]):
                    return True
                if hostname == expr:
                    return True

        return False


class HeaderRegexpFilter(object):
    """
    Matches a regular expression on the headers of an email message.
    """
    def __init__(self, *exprs):
        self.regexps = [re.compile(expr, re.IGNORECASE) for expr in exprs]

    def __call__(self, message):
        for name in message.keys():
            header = '%s: %s' % (name, message.get(name))
            for regexp in self.regexps:
                if regexp.match(header) is not None:
                    return True
        return False


class HeaderRegexpFileFilter(HeaderRegexpFilter):
    """
    Same as HeaderRegexpFilter but loads regexps from a file.
    """
    def __init__(self, path):
        with open(path) as f:
            self.regexps = [re.compile(line.strip(), re.IGNORECASE)
                            for line in f]


class BodyRegexpFilter(object):
    """
    Matches a regular expression on the body of an email message (any part).
    """
    def __init__(self, *exprs):
        self.regexps = [re.compile(expr, re.IGNORECASE) for expr in exprs]

    def __call__(self, message):
        for part in message.walk():
            if not part.get_content_type().startswith('text/'):
                continue

            # Get body for this message part as unicode
            body = part.get_payload(decode=True)
            charset = part.get_charset()
            if not charset:
                charset = 'UTF-8'
            body = body.decode('UTF-8')

            # See if we match
            for regexp in self.regexps:
                if regexp.search(body) is not None:
                    return True

        return False

class BodyRegexpFileFilter(BodyRegexpFilter):
    """
    Same as BodyRegexpFilter but loads regexps from a file.
    """
    def __init__(self, path):
        with open(path) as f:
            self.regexps = [re.compile(line.strip(), re.IGNORECASE)
                            for line in f]
