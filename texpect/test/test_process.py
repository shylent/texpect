'''
@author: shylent
'''
from texpect.protocols import ProcessExpect
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.trial import unittest
import os.path


class DumbProcessProtocol(ProcessExpect):

    def __init__(self, d):
        self.deferred = d
        ProcessExpect.__init__(self, debug=True)

    def connectionMade(self):
        self.deferred.callback(self)


class ProcessTestCase(unittest.TestCase):

    def test_normal_interaction(self):
        def cb(inst):
            d = inst.read_until('llo')
            d.addCallback(lambda res: self.assertEqual(res, 'hello'))
            d.addCallback(lambda ign: inst.write('something'))
            d.addCallback(lambda ign: inst.transport.closeStdin())
            d.addCallback(lambda ign: inst.read_all())
            d.addCallback(lambda res: self.assertEqual(res, 'farewell'))
            d.addCallback(lambda ign: inst.transport.loseConnection())
            return d
        d = Deferred()
        d.addCallback(cb)
        p = DumbProcessProtocol(d)
        reactor.spawnProcess(p, 'python', ['python', '-m', 'mock_process'],
                             path=os.path.dirname(__file__))
        return d
