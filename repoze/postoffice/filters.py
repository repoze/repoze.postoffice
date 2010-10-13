
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
            if '@' not in addr:
                continue

            addr = addr.lower()
            lt = addr.find('<')
            if lt != -1:
                addr = addr[lt+1:addr.rindex('>')]
            hostname = addr.split('@')[1]

            for expr in self.expr.lower().split():
                if expr.startswith('.') and hostname.endswith(expr[1:]):
                    return True
                if hostname == expr:
                    return True

        return False
