"""
@author: shylent
"""
from texpect import TExpect, OutOfSequenceError, EOFReached, \
    RequestInterruptedByConnectionLoss, RequestTimeout, ConnectionAlreadyClosed
from twisted.internet import reactor
from twisted.internet.error import ConnectionDone
from twisted.test.proto_helpers import StringTransport, \
    StringTransportWithDisconnection
from twisted.trial import unittest
import re

foo_pattern = re.compile('foo')
bar_pattern = re.compile('bar')
spam_pattern = re.compile('spam')

class TestBufferProcessing(unittest.TestCase):
    
    def setUp(self):
        self.texpect = TExpect()
        self.texpect._buf = 'foobar'
    
    def test_single_match(self):
        self.assertEqual(foo_pattern.search(self.texpect._buf).groups(),
                         self.texpect._process_buffer([foo_pattern])[1].groups())
    
    #demonstrate, that the patterns are tested in the order, in which the are specified
    def test_multi_match_1(self):
        self.assertEqual(self.texpect._process_buffer([foo_pattern, bar_pattern])[2], 'foo')
    
    def test_multi_match_2(self):
        self.assertEqual(self.texpect._process_buffer([bar_pattern, foo_pattern])[2], 'foobar')
    
    #A pattern, that doesn't match anything yields None
    def test_non_match(self):
        self.assertEqual(self.texpect._process_buffer([spam_pattern]), None)
    
class TestSequence(unittest.TestCase):
    
    def setUp(self):
        self.texpect = TExpect()
        self.texpect.transport = StringTransport()
        self.texpect._buf = 'Welcome to Windows. Press Ctrl-Alt-Delete to begin'
    
    def test_double_read_1(self):
        """
        If the argument of the first request was in the buffer, the errback
        on the second one would've never been called
        (see L{test_wrong_sequence_no_failure}). As the documentation states,
        in such cases the behaviour is undefined
        
        """
        d1 = self.texpect.read_until('toz')
        d2 = self.texpect.read_until('Press')
        return self.failUnlessFailure(d2, OutOfSequenceError)
    
    def test_double_read_2(self):
        d1 = self.texpect.read_until('foobar')
        d2 = self.texpect.expect(['to'])
        return self.failUnlessFailure(d2, OutOfSequenceError)

    def test_wrong_sequence_no_failure(self):
        d1 = self.texpect.read_until('to')
        d2 = self.texpect.read_until('Press')
        
    def test_wrong_sequence_delayed(self):
        """
        Unlike L{test_wrong_sequence_no_failure}, this (rightfully) fails, because by the time
        data arrives, the erroneous second call to L{read_until} was already made
        
        """
        self.texpect._buf = ''
        dc = reactor.callLater(1, self.texpect.applicationDataReceived, 
                          'Welcome to Windows. Press Ctrl-Alt-Delete to begin')
        d1 = self.texpect.read_until('to')
        d2 = self.texpect.read_until('Press')
        self.addCleanup(dc.cancel)
        return self.failUnlessFailure(d2, OutOfSequenceError)
    
    def test_write_after_read(self):
        d1 = self.texpect.read_until('not-in-buffer')
        d2 = self.texpect.write('something')
        return self.failUnlessFailure(d2, OutOfSequenceError)
    
    def test_correct_sequence(self):
        d1 = self.texpect.read_until('to')
        d1.addCallback(lambda res: self.texpect.read_until('Press'))
    
class TestBasicRetrieval(unittest.TestCase):
    
    def setUp(self):
        self.texpect = TExpect()
        self.texpect._buf = 'Welcome to Windows. Press Ctrl-Alt-Delete to begin'
    
    def test_sequential_read(self):
        self.accumulator = ''
        def __cb(res):
            self.accumulator += res
            return res
        d = self.texpect.read_until('Windows')
        d.addCallback(__cb)
        d.addCallback(lambda res: self.texpect.read_until('Delete'))
        d.addCallback(__cb)
        d.addCallback(lambda x: self.assertEqual(self.accumulator,
            'Welcome to Windows. Press Ctrl-Alt-Delete'))
        return d
    
    def test_write(self):
        self.texpect.transport = StringTransport()
        d = self.texpect.read_until('Alt-')
        d.addCallback(self.texpect.write)
        d.addCallback(lambda x: self.assertEqual(self.texpect.transport.value(),
                                'Welcome to Windows. Press Ctrl-Alt-'))
        return d
        
class TestReadAll(unittest.TestCase):
    timeout = 3
    
    def setUp(self):
        self.texpect = TExpect()
        transport = StringTransportWithDisconnection()
        self.texpect.transport = transport
        transport.protocol = self.texpect
        
    def test_closed_connection(self):
        r"""
        There is some data in the buffer and the connection has already closed.
        The call to L{read_all} will return all of the remaining data and
        the promise attribute will be cleared. Any further attemps to make requests
        will result in a L{EOFReached} error.
        
        """
        self.texpect.eof = True
        self.texpect._buf = 'foobar'
        d = self.texpect.read_all()
        d.addCallback(self.assertEqual, 'foobar')
        d.addCallback(lambda x: self.assertIdentical(self.texpect.promise, None))
        d.addCallback(lambda x: self.texpect.read_all())
        return self.failUnlessFailure(d, EOFReached)
    
    def test_working_connection(self):
        def write_and_close():
            self.texpect.applicationDataReceived('second')
            self.texpect.close()
        self.texpect._buf = "first"
        d = self.texpect.read_all()
        reactor.callLater(0.5, self.assertNotIdentical, self.texpect.promise, None)
        reactor.callLater(1.0, write_and_close)
        d.addCallback(self.assertEqual, 'firstsecond')
        
        #Same as in L{test_closed_connection}, check that the instance is reset
        d.addCallback(lambda x: self.assertIdentical(self.texpect.promise, None))
        d.addCallback(lambda x: self.texpect.read_all())
        return self.failUnlessFailure(d, EOFReached)
        

class TestFailedRequests(unittest.TestCase):
    """Test for various conditions, that might result in the L{RequestFailed}-derived
    exceptions being raised.
    
    """
    
    def setUp(self):
        self.texpect = TExpect()
    
    def test_connection_loss_during_request(self):
        """
        The request is in progress and connection is (suddenly) broken
        
        """
        def on_failure(failure):
            self.assertIsInstance(failure.value, RequestInterruptedByConnectionLoss)
            self.assertEqual(failure.value.data, 'something')
            self.assertEqual(failure.value.promise.expecting, [re.compile('foo')])
            return True
        self.texpect._buf = 'something'
        d = self.texpect.expect(['foo'])
        dc = reactor.callLater(1, self.texpect.connectionLost, ConnectionDone())
        d.addErrback(on_failure)
        return d
    
    def test_request_timeout(self):
        """
        The request timed out, perhaps the system on the other side
        didn't produce what we expected
        
        """
        def on_failure(failure):
            self.assertIsInstance(failure.value, RequestTimeout)
            self.assertEqual(failure.value.data, 'something')
            self.assertEqual(failure.value.promise.expecting, [re.compile('foo')])
            return True
        self.texpect._buf = 'something'
        d = self.texpect.expect(['foo'], timeout=0.5)
        d.addErrback(on_failure)
        return d
    
    def test_hopeless_connection(self):
        """
        Connection is already closed by the time this request is made
        and the request cannot be completed at the moment. Since the connection is
        closed, it cannot be completed at all.
        
        """
        def on_failure(failure):
            self.assertIsInstance(failure.value, ConnectionAlreadyClosed)
            self.assertEqual(failure.value.data, 'something')
            self.assertEqual(failure.value.promise.expecting, [re.compile('foo')])
            return True
        self.texpect.eof = True
        self.texpect._buf = 'something'
        d = self.texpect.expect(['foo'])
        d.addErrback(on_failure)
        return d
