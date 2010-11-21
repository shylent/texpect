'''
@author: shylent
'''
from texpect.mixin import ExpectMixin
from twisted.conch import telnet

class TelnetExpect(telnet.Telnet, ExpectMixin):

    def __init__(self, debug=False, timeout=None, _reactor=None):
        ExpectMixin.__init__(self, debug=debug, timeout=timeout, _reactor=_reactor)
        telnet.Telnet.__init__(self)

    def applicationDataReceived(self, data):
        self.expectDataReceived(data)

    def connectionLost(self, reason):
        telnet.Telnet.connectionLost(self, reason)
        ExpectMixin.connectionLost(self, reason)
