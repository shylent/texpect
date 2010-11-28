
texpect
==
Automate interactive sessions using [Twisted](http://twistedmatrix.com/).

##Description
TExpect attempts to provide an interface, similar to [telnetlib.Telnet](http://docs.python.org/library/telnetlib.html#telnetlib.Telnet) from python standard library, which is, in turn inspired by [expect](http://expect.sourceforge.net/) (I think).
Since most of the time during the interactive session is waiting for desired data, Twisted really does shine here with its asynchronous I/O.

An interactive session is represented by an instance of a Expect-derived class. When a request is made to the session, a Deferred is returned, which is then fired with the result of the request. In case of a failed request, an error is returned via an errback.

This way one does not have to block while waiting for the result of the request or for the timeout.

Ready-to-use implementations using twisted.conch.telnet.Telnet and twisted.internet.protocol.ProcessProtocol are provided.

##Example


    from twisted.internet import reactor
    from twisted.internet.protocol import ClientCreator
    from texpect.protocols import TelnetExpect
    import sys
    
    host = "en.wikipedia.org"
    port = 80
    
    cc = ClientCreator(reactor, TelnetExpect)
    c = cc.connectTCP(host, port)
    def do_interact(inst):
        d = inst.write("HEAD /wiki/Main_Page HTTP/1.1\r\n"
                       "Host: en.wikipedia.org\r\n\r\n")
        d.addCallback(lambda ign: inst.read_all())
        d.addCallback(sys.stdout.write)
    c.addCallback(do_interact)
    
    reactor.run()

Obviously, this is not the optimal use case, as this is better done using, for example, [t.w.http.HTTPClient](http://twistedmatrix.com/documents/current/api/twisted.web.http.HTTPClient.html), but still it shows the basic usage of the API.

##Documentation
The API is fully documented using [epydoc](http://epydoc.sourceforge.net/). You can generate the documentation from the source using something along the lines of `epydoc -o doc --html texpect`.

##Tests
A test suite is included (texpect.test module).

##Future
There are some features, that I'd certainly like to see implemented.  
In order of importance:

- Support [read_some](http://docs.python.org/library/telnetlib.html#telnetlib.Telnet.read_some) request.
- Support ssh out of the box.
- Support direct interaction using manhole.
