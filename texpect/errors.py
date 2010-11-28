'''
@author: shylent
'''


class ExpectError(Exception):
    """Base class for errors, specific to this module"""
    pass

class OutOfSequenceError(ExpectError):
    """Raised when an attempt to initialize a request is made, while there is
    a request pending.
    
    """
    pass

class EOFReached(ExpectError):
    """Raised when the connection is closed and no data is available."""
    pass


class RequestFailed(ExpectError):
    """Request failed for whatever reason.
    
    @ivar data: Data, that was collected up to the point of failure
    @type data: C{str}
    @ivar promise: Request, that caused this timeout
    @type promise: L{Promise}
    
    """

    def __init__(self, msg='Request failed', data=None, promise=None):
        """
        @param msg: A message for this exception. Default: 'Request timed out'
        @type msg: C{str}
        @param data: Data, that was collected so far. Default: C{None}
        @type data: C{str}
        @param promise: Request, that caused this timeout. Default: C{None}
        @type promise: L{Promise}
        
        """
        self.data = data
        self.promise = promise
        super(RequestFailed, self).__init__(msg)


class RequestTimeout(RequestFailed):
    """Request timed out"""
    def __init__(self, msg='Request timed out', data=None, promise=None):
        super(RequestTimeout, self).__init__(msg, data, promise)


class RequestInterruptedByConnectionLoss(RequestFailed):
    """Connection was lost, while the request was in progress and there is no
    way to complete the request, - nothing matched so far.
    
    """
    def __init__(self, msg='Connection was lost, while the request was in progress',
                 data=None, promise=None):
        super(RequestInterruptedByConnectionLoss, self).__init__(msg, data, promise)


class ConnectionAlreadyClosed(RequestFailed):
    """A request is being initialized, but the connection is already closed and
    the request cannot be successfully completed.
    
    """
    def __init__(self, msg='Connection is closed, can not complete the request.',
                 data=None, promise=None):
        super(ConnectionAlreadyClosed, self).__init__(msg, data, promise)
