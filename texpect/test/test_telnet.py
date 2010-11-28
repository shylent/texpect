'''
@author: shylent
'''
from texpect.protocols import TelnetExpect
from twisted.internet.protocol import Protocol, ServerFactory, ClientCreator
from twisted.trial import unittest


class OneShotServer(Protocol):

    def connectionMade(self):
        self.transport.write(self.factory.greeting)

    def dataReceived(self, data):
        for byte in data:
            self.transport.write(byte)
        self.transport.write(self.factory.response)
        if self.factory._disconnect:
            self.loseConnection(self)

    def loseConnection(self, reason):
        self.transport.loseConnection()

class TelnetTestCase(unittest.TestCase):

    def setUp(self):
        self.server_factory = ServerFactory()
        self.server_factory.protocol = OneShotServer

    def go(self, greeting='', response='', disconnect=False):
        from twisted.internet import reactor
        self.server_factory.response = response
        self.server_factory.greeting = greeting
        self.server_factory._disconnect = disconnect
        self.port = reactor.listenTCP(2300, self.server_factory)
        cc = ClientCreator(reactor, TelnetExpect)

        self.addCleanup(self.port.stopListening)

        return cc.connectTCP('localhost', 2300)

    def test_normal_operation(self):
        def cb(inst):
            d = inst.read_until('ello')
            d.addCallback(lambda res: self.assertEqual(res, 'hello'))
            d.addCallback(lambda ign: inst.write('something'))
            d.addCallback(lambda ign: inst.read_all())
            d.addCallback(lambda res: self.assertEqual(res, 'somethingfarewell'))
            return d
        d = self.go('hello', 'farewell', True)
        d.addCallback(cb)
        return d
