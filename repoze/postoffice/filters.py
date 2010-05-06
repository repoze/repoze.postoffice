
class ToHostnameFilter(object):
    """
    Matches the hostname of the email address in the 'To:' header of an email
    message.
    """
    def __init__(self, expr):
        self.expr = expr

    def __call__(self, message):
        if 'To' not in message:
            return False

        addr = message['To'].lower()
        if '@' not in addr:
            return False

        lt = addr.find('<')
        if lt != -1:
            addr = addr[lt+1:addr.rindex('>')]
        hostname = addr.split('@')[1]

        expr = self.expr.lower()
        if expr.startswith('.'):
            return hostname.endswith(expr[1:])
        return hostname == expr
