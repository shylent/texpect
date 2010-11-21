"""
@author: shylent
"""
from texpect.errors import (RequestInterruptedByConnectionLoss, RequestTimeout,
    OutOfSequenceError, EOFReached, ConnectionAlreadyClosed)
from twisted.internet.defer import fail, Deferred, maybeDeferred
from twisted.python import log
from twisted.python.failure import Failure
import re


class Promise(Deferred):
    r"""Base class for Deferred extensions, that are used in this module
    A request in progress.

    """

    def __init__(self, timeout=None):
        r"""
        @param timeout: Timeout object.
        @type timeout: Any object, providing L{IDelayedCall<twisted.internet.interfaces.IDelayedCall>}

        """
        self._timeout = timeout
        Deferred.__init__(self)

    def callback(self, *args, **kwargs):
        if self._timeout is not None and self._timeout.active():
            self._timeout.cancel()
        return Deferred.callback(self, *args, **kwargs)

    def errback(self, *args, **kwargs):
        if self._timeout is not None and self._timeout.active():
            self._timeout.cancel()
        return Deferred.errback(self, *args, **kwargs)

    def __str__(self):
        return self.__class__.__name__

class ReadAll(Promise):
    pass

class ReadLazy(Promise):
    pass


class Expect(Promise):
    """Base class for requests, that provide the 'expect' behaviour.

    @ivar expecting: A list of patterns, that we are 'expecting' (sorry).
    @type expecting: C{list}
    @ivar as_tuple: Whether the callback should be called with a tuple or not. Tuple
    items are: the index in the list of patterns of the pattern, that matched,
    the match object, the data up to and including the match. If L{is_tuple} is C{False},
    the callback will only be called with the data up to and including the match.
    @type as_tuple: C{bool}

    """

    def __init__(self, expect, timeout=None, as_tuple=True):
        """
        @param expect: List of patterns, that will be matched against the buffer
        @param timeout: Timeout in seconds for this request.
        @type timeout:C{int}
        @param as_tuple: If set to False, first two items of the result are dropped
        and only the gathered data is returned via the callback.
        @type as_tuple: C{bool}

        """
        Promise.__init__(self, timeout)
        self.expecting = expect
        self.as_tuple = as_tuple

    def callback(self, res, *args, **kwargs):
        if not self.as_tuple and not isinstance(res, basestring):
            res = res[2]
        return Promise.callback(self, res, *args, **kwargs)

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, ', '.join("'" + p.pattern + "'" for p in self.expecting))


class ReadUntil(Expect):

    def __init__(self, expect, timeout=None, as_tuple=False):
        Expect.__init__(self, expect, timeout, as_tuple)


class ExpectMixin(object):
    r"""This class attempts to implement an U{expect<http://expect.sourceforge.net/>}-like
    interface, similar to U{telnetlib<http://docs.python.org/library/telnetlib.html>}, but
    in such a way so as to be usable from twisted using twisted's usual machinery: 
    asynchronous I/O, Deferreds and so on.

    It exposes a set of methods (so-called 'requests'), that each returns a L{Promise},
    which will be fired, when certain conditions (specific for each request) are met.

    @attention: Only one request may be active at a time. If this restriction is violated,
    the connection will be closed immediately. You may use multiple patterns, as an
    argument to L{expect} to specify multiple conditions.

    Use callback chains to issue requests sequentially.

    Wrong::

        t = ExpectMixin()
        d1 = t.read_until('foo')
        d2 = t.read_until('bar')
        # Behaviour is undefined, depends on immediate availability
        # of data in the buffer, network latency and so on

    Right::

        t = ExpectMixin()
        d = t.read_until('foo')
        d.addCallback(lambda res: t.read_until('bar'))

    This also applies to writing to the transport, which can be only done when
    no requests are in progress.

    @note: Some L{telnetlib.Telnet}'s functionality is currently missing, namely L{read_some},
    that is supposed to return I{at least one byte} of data. Session interaction, which is
    similar to Expect's U{interact<http://wiki.tcl.tk/3914>} command is also missing. It may be
    implemented later using L{manhole}.

    @ivar timeout: Default timeout value.
    @type timeout: C{int} 
    @ivar debug: Debug flag
    @type debug: C{bool}
    @ivar _buf: Internal buffer, which is flushed each time a request is completed.
    @type _buf: C{str}
    @ivar _debug_buf: Buffer, that holds all the received data
    @type _debug_buf: C{str}
    @ivar promise: Current pending request
    @type promise: L{Promise} or C{None}

    """

    def __init__(self, debug=False, timeout=None, _reactor=None, *args, **kwargs):
        r"""
        @param debug: Enable debug mode, - there will be more log messages
        and the entire buffer will be kept in the _debug_buf attribute indefinitely.
        @param timeout: Set a default timeout in seconds for all requests, wherever applicable.
        @type timeout:C{int}

        """
        if _reactor is not None:
            self._reactor = _reactor
        else:
            from twisted.internet import reactor
            self._reactor = reactor
        self.timeout = timeout
        self.debug = debug
        self._buf = self._debug_buf = ''
        self.promise = None
        self.eof = False

    def connectionLost(self, reason):
        r"""Connection loss is handled here. When subclassing, one should take care
        to call the parent's L{connectionLost} in order for the default connection
        loss handling (and also L{twisted.conch.telnet.Telnet}'s connection loss
        handling) to take place.

        """
        reason = getattr(reason, 'value', reason)
        log.msg("Connection lost, reason: %s" % reason)
        self.eof = True
        buf = self._buf
        self._buf = ''
        promise = self.promise
        self.promise = None
        if isinstance(promise, ReadAll):
            promise.callback(buf)
        elif isinstance(promise, Expect):
            promise.errback(Failure(RequestInterruptedByConnectionLoss(data=buf, promise=promise)))

    def expectDataReceived(self, data):
        if self.debug:
            log.msg('Received data: %r' % data)
        self._buf += data
        if self.debug:
            self._debug_buf += data
        if isinstance(self.promise, Expect):
            res = self._process_buffer(self.promise.expecting)
            if res:
                self._buf = self._buf[res[1].end():]
                promise = self.promise
                self.promise = None
                promise.callback(res)

    def _process_buffer(self, pattern_list):
        r"""Process the buffer, trying the patterns provided. In case of the match,
        the result is returned as a 3-tuple, where the items are: the index
        in the list of patterns of the pattern, that matched, the match object,
        the data up to and including the match.

        This method is considered private and should not be called directly.

        @param pattern_list: A list of regex objects to check the buffer against
        @rtype: C{(int, SRE_Match, str)} or C{None}

        """
        for pattern_index, pattern in enumerate(pattern_list):
            s = pattern.search(self._buf)
            if s:
                result = self._buf[:s.end()]
                if self.debug:
                    log.msg('Pattern %s matched - returning (%r, %r, %r)' %
                            (pattern.pattern, pattern_index, s, result))
                return (pattern_index, s, result)

    def _handle_timeout(self):
        r"""Handle the timeout according to request type. This method is considered
        private and should not be called directly.

        """
        if self.debug:
            log.msg('Timeout reached, terminating promise %s' % self.promise)
        promise = self.promise
        self.promise = None
        buf = self._buf
        self._buf = ''
        if isinstance(promise, Expect):
            promise.errback(Failure(RequestTimeout(data=buf, promise=promise)))

    def read_lazy(self, _promise_class=ReadLazy):
        r"""A request to return all data, that is currently in the buffer.

        It doesn't return the data directly only to stay consistent with the rest
        of the methods.
        
        @param _promise_class: A L{Promise} class, that will be used for this request. This
        argument is used internally and should not be used directly.

        @return: A L{Deferred} (L{ReadLazy}), that has already had its callback called
        with the data in the buffer (possibly an empty string).
        Errback argument types:
            - L{EOFReached}: if the connection is already closed by the time the
            request is made and there is no data available
            - L{OutOfSequenceError}: if there is another request in progress
        @rtype: L{ReadLazy}

        """
        promise = _promise_class()
        if self.promise is not None:
            promise.errback(Failure(OutOfSequenceError('Unable to process request, '
                                'there is another one pending: %s' % self.promise)))
            self.transport.loseConnection()
            return promise
        if not self._buf and self.eof:
            promise.errback(Failure(EOFReached('The connection is closed and no data is available')))
            return promise
        else:
            data = self._buf
            self._buf = ''
            promise.callback(data)
            return promise


    def read_all(self):
        r"""A request to read all data until the connection is lost.

        @return: A L{Deferred} (L{ReadAll}), that will be fired with the contents
        of the buffer, when the connection closes (possibly an empty string).
        Errback argument types:
            - L{EOFReached}: if the connection is already closed by the time the
            request is made and there is no data available
            - L{OutOfSequenceError}: if there is another request in progress
        @rtype: L{ReadAll}

        """
        if self.promise is not None:
            failed = fail(OutOfSequenceError('Unable to process request, '
                                'there is another one pending: %s' % self.promise))
            self.transport.loseConnection()
            return failed
        if self.eof:
            return self.read_lazy(_promise_class=ReadAll)
        else:
            self.promise = ReadAll()
            return self.promise

    def expect(self, pattern_list, timeout=None, _promise_class=Expect):
        r"""A request to read data until a pattern from a pattern list matches the buffer.

        The patterns are tested in the order, in which they are present in the list.
        If the greedy quantifiers are used, the result is indeterministic
        and depends on the fragmentation of incoming data.

        If the pattern matches, the callback will be fired with a tuple of
        three items as an argument, the items are: the index in the list of patterns 
        of the pattern, that matched, the match object, the data up to and including the match.


        @param pattern_list: A list of strings or compiled regular expression objects.
        @param timeout: A number of seconds to wait for the match. Overrides the instance
        default.
        @type timeout: C{int}
        @param _promise_class: A L{Promise} class, that will be used for this request. This
        argument is used internally and should not be used directly.

        @return: L{Expect} instance, that will be fired with a tuple of three items.
        The items are: the index in the list of patterns of the pattern, that matched, 
        the match object, the data up to and including the match.
        Errback argument types:
            - L{OutOfSequenceError}: when the request is issued and another request is in progress
            - L{EOFReached}: if the connection is already closed by the time the
            request is made and there is no data available
            - L{ConnectionAlreadyClosed}: when the request is issued, but the connection
            is closed and existing data is not sufficient to satisfy the request
            - L{RequestInterruptedByConnectionLoss}: the connection is closed, the
            request is in progress and nothing has matched
            - L{RequestTimeout}: when the request has timed out
        @rtype: L{Expect}

        """
        if self.promise is not None:
            failed = fail(OutOfSequenceError('Unable to process request, '
                                           'there is another one pending: %s' % self.promise))
            self.transport.loseConnection()
            return failed
        #Be nice, if a string was passed (should've been a list), make a list out of it
        if isinstance(pattern_list, basestring):
            pattern_list = [pattern_list]

        #Compile the patterns
        expecting = []
        for pattern in pattern_list:
            if isinstance(pattern, basestring):
                pattern = re.compile(pattern)
            expecting.append(pattern)

        self.promise = _promise_class(expecting)
        promise = self.promise
        #Attempt to match right away
        res = self._process_buffer(self.promise.expecting)

        if self.eof:
            if not self._buf:
                promise.errback(Failure(EOFReached('The connection is closed and no data is available')))
                return promise
            else:
                if not res:
                    buf = self._buf
                    self._buf = ''
                    self.promise = None
                    promise.errback(Failure(ConnectionAlreadyClosed(data=buf, promise=promise)))
                    return promise

        if res:
            self._buf = self._buf[res[1].end():]
            self.promise = None
            promise.callback(res)
        else:
            if timeout is None and self.timeout is not None:
                timeout = self.timeout
            if timeout is not None:
                promise._timeout = self._reactor.callLater(timeout,
                                                           self._handle_timeout)
        return promise

    def read_until(self, expected, timeout=None):
        r"""A request to read until a specified pattern matches. This method is
        provided to mimic telnetlib.Telnet's read_until method.

        @param expected: A pattern, that we are expecting
        @type expected: C{str} or C{SRE_Pattern}
        @param timeout: A number of seconds to wait for the match, C{None} to wait
        indefinitely. Overrides the instance default.
        @type timeout: C{int}

        @return: L{Expect} instance, that will be fired with a tuple of three items.
        The items are: the index in the list of patterns of the pattern, that matched, 
        the match object, the data up to and including the match.
        Errback argument types:
            - L{OutOfSequenceError}: when the request is issued and another request is in progress
            - L{EOFReached}: if the connection is already closed by the time the
            request is made and there is no data available
            - L{ConnectionAlreadyClosed}: when the request is issued, but the connection
            is closed and existing data is not sufficient to satisfy the request
            - L{RequestInterruptedByConnectionLoss}: the connection is closed, the
            request is in progress and nothing has matched
            - L{RequestTimeout}: when the request has timed out
        @rtype: L{Expect}

        """
        return self.expect([expected], timeout, _promise_class=ReadUntil)

    def write(self, bytes):
        r"""Write data to the transport.

        Returns a L{Deferred} to stay consistent with other methods.

        @param bytes: Data to write to the transport
        @return: A L{Deferred}.
        Errback argument types:
            - L{OutOfSequenceError}: when the request is issued and another request is in progress
        @rtype: L{Deferred}

        """
        if self.promise is not None:
            failure = fail(OutOfSequenceError('Unable to write, request is in progress: %r' % self.promise))
            self.transport.loseConnection()
            return failure
        return maybeDeferred(self.transport.write, bytes)

    def close(self):
        """Close the connection immediately.

        @rtype: L{Deferred}
        """
        log.msg('Closing connection as requested')
        return maybeDeferred(self.transport.loseConnection)
