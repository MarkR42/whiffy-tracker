# -*- coding: utf-8 -*-
from __future__ import print_function

import dnslib
from dnslib import RR,QTYPE,RCODE,TXT,parse_time
from dnslib.label import DNSLabel
from dnslib.server import DNSServer,DNSHandler,BaseResolver,DNSLogger

import time
import datetime
import socket
import struct

class DynamicResolver(BaseResolver):

    possible_origins = (
        'example.test.',
        'mr8266.tk.'
        )

    def __init__(self):
        self.ttl = 120

    def resolve(self,request,handler):
        reply = request.reply()
        qname = request.q.qname
        # Check it's our zone
        good_origin = False
        for origin in self.possible_origins:
            suffix = '.' + str(origin)
            if str(qname).endswith(suffix):
                good_origin = origin
        
        if not good_origin:
            reply.header.rcode = RCODE.SERVFAIL
            return reply
            
        local_name = str(qname)[:(- len(good_origin) - 1)]
        
        def reply_ipv4(request, ip, ttl=self.ttl):
            reply = request.reply()
            qname = request.q.qname
            reply.add_answer(RR(qname, QTYPE.A, ttl=ttl,
                rdata=dnslib.A(ip)))
            return reply
           
        with open('dnslog.txt', 'a') as f:
          print(local_name, file=f) 
        if local_name in ('test', 'test1'):
            return reply_ipv4(request, '127.0.0.1')
        if local_name == 'test2':
            return reply_ipv4(request, '127.0.0.2')
        if local_name == 'time':
            # short ttl on time.
            return reply_ipv4(request, self.time_ip(), 5)
        # Otherwise:
        reply.header.rcode = RCODE.NXDOMAIN
        return reply
        
    def time_ip(self):
        # Return a "ipv4 address" which contains the number of 
        # seconds since 2000-01-01 00:00 GMT
        epoch = datetime.datetime(2000,1,1)
        since_epoch = datetime.datetime.now() - epoch
        secs_since_epoch = int(since_epoch.total_seconds())
        return socket.inet_ntoa(struct.pack('>I', int(secs_since_epoch)))

if __name__ == '__main__':

    resolver = DynamicResolver()

    address = ''
    port = 5353
    print("Starting Resolver")
    
    udp_server = None
    for port in (53, 5353):
        try:
            udp_server = DNSServer(resolver,
                                   port=port,
                                   address=address)
            break
        except PermissionError:
            if port == 5353:
                raise # Otherwise try again
    udp_server.start_thread()

    while udp_server.isAlive():
        time.sleep(1)

