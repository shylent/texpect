"""
@author: shylent
"""
from texpect.errors import (EOFReached, OutOfSequenceError, 
    ConnectionAlreadyClosed, RequestInterruptedByConnectionLoss, RequestTimeout)
from texpect.mixin import Expect, ExpectMixin
from twisted.internet import reactor
from twisted.test.proto_helpers import StringTransportWithDisconnection
from twisted.trial import unittest
import re


class ProcessBufferTestCase(unittest.TestCase):
    
    def setUp(self):
        self.t = ExpectMixin()
        self.t._buf = 'foobar'
    
    def test_single_pattern(self):
        # I have no idea how to compare match objects
        res = self.t._process_buffer([re.compile('foo')])
        self.assertEqual((res[0], res[2]), (0, 'foo'))
        
        self.assertIdentical(self.t._process_buffer([re.compile('baz')]), None)
        
    def test_multiple_patterns(self):
        res = self.t._process_buffer([re.compile('foo'), re.compile('foobar')])
        self.assertEqual((res[0], res[2]), (0, 'foo'))
        res = self.t._process_buffer([re.compile('baz'), re.compile('bar')])
        self.assertEqual((res[0], res[2]), (1, 'foobar'))

class ReadLazyTestCase(unittest.TestCase):
    
    def setUp(self):
        self.t = ExpectMixin()
        self.t.transport = StringTransportWithDisconnection()
        self.t.transport.protocol = self.t
        
    def test_data_immediately_available(self):
        def cb(res):
            self.assertEqual(res, 'foo')
            self.assertIdentical(self.t.promise, None)
        self.t._buf = 'foo'
        d = self.t.read_lazy()
        self.failUnlessTrue(d.called)
        d.addCallback(cb)
    
    def test_data_not_available(self):
        def cb(res):
            self.assertEqual(res, '')
            self.assertIdentical(self.t.promise, None)
        d = self.t.read_lazy()
        self.failUnlessTrue(d.called)
        d.addCallback(cb)
    
    def test_connection_closed_no_data(self):
        self.t.eof = True
        d = self.t.read_lazy()
        self.failUnlessTrue(d.called)
        self.failUnlessFailure(d, EOFReached)
    
    def test_connection_closed_with_data(self):
        self.t.eof = True
        def cb(res):
            self.assertEqual(res, 'foo')
            self.assertIdentical(self.t.promise, None)
        self.t._buf = 'foo'
        d = self.t.read_lazy()
        self.failUnlessTrue(d.called)
        d.addCallback(cb)
    
    def test_out_of_sequence(self):
        self.t._buf = 'foo'
        d1 = self.t.read_all()
        d2 = self.t.read_lazy()
        self.failUnlessTrue(d1.called)
        self.failUnlessTrue(d2.called)
        d1.addCallback(lambda res: self.assertEqual(res, 'foo'))
        self.failUnlessFailure(d2, OutOfSequenceError)

class ReadAllTestCase(unittest.TestCase):
    
    def setUp(self):
        self.t = ExpectMixin()
        self.t.transport = StringTransportWithDisconnection()
        self.t.transport.protocol = self.t
    
    def test_active_connection_with_data(self):
        self.t._buf = 'foobar'
        def cb(res):
            self.assertEqual(res, 'foobar')
        d = self.t.read_all()
        self.failIf(d.called)
        d.addCallback(cb)
        reactor.callLater(0.5, self.t.transport.loseConnection)
        return d
    
    def test_active_connection_without_data(self):
        self.t._buf = ''
        def cb(res):
            self.assertEqual(res, '')
        d = self.t.read_all()
        self.failIf(d.called)
        d.addCallback(cb)
        reactor.callLater(0.5, self.t.transport.loseConnection)
        return d
    
    def test_closed_connection_with_data(self):
        self.t._buf = 'foobar'
        self.t.eof = True
        def cb(res):
            self.assertEqual(res, 'foobar')
            self.assertIdentical(self.t.promise, None)
        d = self.t.read_all()
        self.failUnless(d.called)
        d.addCallback(cb)
        
    def test_closed_connection_without_data(self):
        self.t._buf = ''
        self.t.eof = True
        def cb(res):
            self.assertEqual(res, 'foobar')
            self.assertIdentical(self.t.promise, None)
        d = self.t.read_all()
        self.failUnless(d.called)
        self.failUnlessFailure(d, EOFReached)
    
    def test_out_of_sequence(self):
        self.t._buf = 'foo'
        d1 = self.t.read_all()
        d2 = self.t.read_all()
        self.failUnlessTrue(d1.called)
        self.failUnlessTrue(d2.called)
        d1.addCallback(lambda res: self.assertEqual(res, 'foo'))
        self.failUnlessFailure(d2, OutOfSequenceError)
    
class ExpectTestCase(unittest.TestCase):
    
    def setUp(self):
        self.t = ExpectMixin()
        self.t.transport = StringTransportWithDisconnection()
        self.t.transport.protocol = self.t

    def test_closed_connection_no_match_no_data(self):
        self.t._buf = ''
        self.t.eof = True
        d = self.t.expect(['baz'])
        self.failUnless(d.called)
        self.failUnlessFailure(d, EOFReached)
    
    def test_closed_connection_no_match(self):
        self.t._buf = 'foobar'
        self.t.eof = True
        d = self.t.expect(['baz'])
        self.failUnless(d.called)
        def eb(fail):
            self.assertIsInstance(fail.value, ConnectionAlreadyClosed)
            self.assertEqual(fail.value.data, 'foobar')
            self.assertEqual(fail.value.promise.expecting[0].pattern, 'baz')
            self.assertIsInstance(fail.value.promise, Expect)
            self.assertEqual(self.t._buf, '')
            self.assertIdentical(self.t.promise, None)
        d.addErrback(eb)
    
    def test_closed_connection_match(self):
        self.t._buf = 'foobar'
        self.t.eof = True
        d = self.t.expect(['foo'])
        self.failUnless(d.called)
        def cb(res):
            (ind, data) = (res[0], res[2])
            self.assertEqual(ind, 0)
            self.assertEqual(data, 'foo')
            self.assertEqual(self.t._buf, 'bar')
            self.assertIdentical(self.t.promise, None)
        d.addCallback(cb)
        
    
    def test_active_connection_immediate_match(self):
        self.t._buf = 'foobar'
        d = self.t.expect(['foo'])
        self.failUnless(d.called)
        def cb(res):
            (ind, data) = (res[0], res[2])
            self.assertEqual(ind, 0)
            self.assertEqual(data, 'foo')
            self.assertEqual(self.t._buf, 'bar')
            self.assertIdentical(self.t.promise, None)
        d.addCallback(cb)
        
    def test_active_connection_delayed_match(self):
        self.t._buf = 'foobar'
        d = self.t.expect(['baz'])
        self.failIf(d.called)
        reactor.callLater(0.5, self.t.expectDataReceived, 'bazspam')
        def cb(res):
            (ind, data) = (res[0], res[2])
            self.assertEqual(ind, 0)
            self.assertEqual(data, 'foobarbaz')
            self.assertEqual(self.t._buf, 'spam')
            self.assertIdentical(self.t.promise, None)
        d.addCallback(cb)
        return d
    
    def test_active_connection_delayed_no_match(self):
        self.t._buf = 'foobar'
        d = self.t.expect(['spam'])
        self.failIf(d.called)
        reactor.callLater(0.5, self.t.expectDataReceived, 'baz')
        def check():
            self.assertIsInstance(self.t.promise, Expect)
            self.assertEqual(self.t._buf, 'foobarbaz')
            self.failIf(d.called)
            d.callback(None)
        reactor.callLater(1.0, check)
        return d
    
    def test_connection_loss_no_match(self):
        self.t._buf = 'foobar'
        d = self.t.expect(['spam'])
        self.failIf(d.called)
        reactor.callLater(0.5, self.t.transport.loseConnection)
        def eb(fail):
            self.assertIsInstance(fail.value, RequestInterruptedByConnectionLoss)
            self.assertEqual(fail.value.data, 'foobar')
            self.assertEqual(fail.value.promise.expecting[0].pattern, 'spam')
            self.assertIsInstance(fail.value.promise, Expect)
            self.assertEqual(self.t._buf, '')
            self.assertIdentical(self.t.promise, None)
        d.addErrback(eb)
        return d  
        
    def test_request_timeout(self):
        self.t._buf = 'foobar'
        d = self.t.expect(['spam'], timeout=0.5)
        self.failIf(d.called)
        def eb(fail):
            self.assertIsInstance(fail.value, RequestTimeout)
            self.assertEqual(fail.value.data, 'foobar')
            self.assertEqual(fail.value.promise.expecting[0].pattern, 'spam')
            self.assertIsInstance(fail.value.promise, Expect)
            self.assertEqual(self.t._buf, '')
            self.assertIdentical(self.t.promise, None)
        d.addErrback(eb)
        return d

    def test_out_of_sequence(self):
        self.t._buf = 'foo'
        d1 = self.t.read_all()
        d2 = self.t.expect(['bar'])
        self.failUnlessTrue(d1.called)
        self.failUnlessTrue(d2.called)
        d1.addCallback(lambda res: self.assertEqual(res, 'foo'))
        self.failUnlessFailure(d2, OutOfSequenceError)

class ReadUntilTestCase(unittest.TestCase):
    
    def setUp(self):
        self.t = ExpectMixin()
        self.t.transport = StringTransportWithDisconnection()
        self.t.transport.protocol = self.t
    
    def test_active_connection_immediate_match(self):
        self.t._buf = 'foobar'
        d = self.t.read_until('foo')
        self.failUnless(d.called)
        def cb(res):
            self.assertEqual(res, 'foo')
            self.assertEqual(self.t._buf, 'bar')
            self.assertIdentical(self.t.promise, None)
        d.addCallback(cb)
    
    def test_active_connection_delayed_match(self):
        self.t._buf = 'foobar'
        d = self.t.read_until('baz')
        self.failIf(d.called)
        reactor.callLater(0.5, self.t.expectDataReceived, 'bazspam')
        def cb(res):
            self.assertEqual(res, 'foobarbaz')
            self.assertEqual(self.t._buf, 'spam')
            self.assertIdentical(self.t.promise, None)
        d.addCallback(cb)
        return d
    
    def test_out_of_sequence(self):
        self.t._buf = 'foo'
        d1 = self.t.read_all()
        d2 = self.t.read_until('bar')
        self.failUnlessTrue(d1.called)
        self.failUnlessTrue(d2.called)
        d1.addCallback(lambda res: self.assertEqual(res, 'foo'))
        self.failUnlessFailure(d2, OutOfSequenceError)
        

class WriteTestCase(unittest.TestCase):
    
    def setUp(self):
        self.t = ExpectMixin()
        self.t.transport = StringTransportWithDisconnection()
        self.t.transport.protocol = self.t
    
    def test_write(self):
        self.t.write('bar')
        self.assertEqual(self.t.transport.io.getvalue(), 'bar')
    
    def test_out_of_sequence(self):
        self.t._buf = 'foo'
        d1 = self.t.read_all()
        d2 = self.t.write('bar')
        self.failUnlessTrue(d1.called)
        self.failUnlessTrue(d2.called)
        d1.addCallback(lambda res: self.assertEqual(res, 'foo'))
        self.failUnlessFailure(d2, OutOfSequenceError)
