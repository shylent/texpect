'''
@author: shylent
'''
from texpect.mixin import ExpectMixin
from twisted.conch import telnet
from twisted.internet.protocol import ProcessProtocol


class TelnetExpect(telnet.Telnet, ExpectMixin):

    def __init__(self, debug=False, timeout=None, _reactor=None):
        ExpectMixin.__init__(self, debug=debug, timeout=timeout, _reactor=_reactor)
        telnet.Telnet.__init__(self)

    def applicationDataReceived(self, data):
        self.expectDataReceived(data)

    def connectionLost(self, reason):
        telnet.Telnet.connectionLost(self, reason)
        ExpectMixin.connectionLost(self, reason)


class ProcessExpect(ProcessProtocol, ExpectMixin):

    def __init__(self, debug=False, timeout=None, _reactor=None):
        ExpectMixin.__init__(self, debug=debug, timeout=timeout, _reactor=_reactor)

    def outReceived(self, data):
        self.expectDataReceived(data)

    def outConnectionLost(self):
        ExpectMixin.connectionLost(self, "stdout closed")
