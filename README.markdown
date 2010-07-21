
texpect
==
Automate interactive sessions using [Twisted](http://twistedmatrix.com/).

##Description
TExpect attempts to provide an interface, similar to [telnetlib.Telnet](http://docs.python.org/library/telnetlib.html#telnetlib.Telnet) from python standard library, which is, in turn inspired by [expect](http://expect.sourceforge.net/) (I think). Since most of the time during the interactive session is waiting for desired data, Twisted really does shine here with its asynchronous I/O.

An interactive session is represented by a TExpect instance. When a request is made to the session, a Deferred is returned, which is then fired with the result of the request. In case of a failed request, an error is returned via an errback.

This way one does not have to block while waiting for the result of the request or for the timeout.

##Example


    from twisted.internet import reactor
    from twisted.internet.protocol import ClientCreator
    from texpect import TExpect
    import sys
    
    host = "en.wikipedia.org"
    port = 80
    
    cc = ClientCreator(reactor, TExpect)
    c = cc.connectTCP(host, port)
    def do_interact(inst):
        d = inst.write("HEAD /wiki/Main_Page HTTP/1.1\r\n"
                       "Host: en.wikipedia.org\r\n\r\n")
        d.addCallback(lambda ign: inst.read_all())
        d.addCallback(sys.stdout.write)
    c.addCallback(do_interact)
    
    reactor.run()

Obviously, this is not the optimal use case for TExpect, as this is better done using, for example, [t.w.http.HTTPClient](http://twistedmatrix.com/documents/current/api/twisted.web.http.HTTPClient.html), but still it shows the basic usage of the API.

##Documentation
The API is fully documented using [epydoc](http://epydoc.sourceforge.net/). You can generate the documentation from the source using something along the lines of `epydoc -o doc --html texpect`.

##Tests
A test suite is included (texpect.test module).

##Future
There are some features, that I'd certainly like to see implemented.  
In order of importance:

- Abstract the API away from [t.c.telnet.Telnet](http://twistedmatrix.com/documents/current/api/twisted.conch.telnet.Telnet.html). In fact, the API is in no way specific to telnet - it can use anything, that implements [IProtocol](http://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IProtocol.html), and has something, that you can write to, which is, well.. a lot of things. This will not affect the API much, only the initialization/teardown part.
- Support [read_some](http://docs.python.org/library/telnetlib.html#telnetlib.Telnet.read_some) request.
- Support direct interaction using manhole.
