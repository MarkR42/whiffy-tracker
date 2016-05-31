#!/usr/bin/env python3
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
import sqlite3
import collections

class DataSaver():
    db_filename = 'messages.sqlite3'

    def __init__(self):
        self.chunks_by_id = collections.defaultdict(list)
        # fail-fast
        db = self.init_db()
        db.close() 

    def store_name(self, name):
        """
            A dns name, is the local part (without domain).

            Check that it's one we're interested in, and store
            in memory until we have a complete packet,
            identified by the "eom" name. 

            Once we have a complete packet, store the packet in sqlite.
        """
        bits = name.split('.', 1)
        if len(bits) > 1:
            info, chunk_id = bits
            self.chunks_by_id[chunk_id].append(info)
            if info.lower() == 'eom':
                self.save_chunk(chunk_id)

    def save_chunk(self, chunk_id):
        db = self.init_db()
        chunk = self.chunks_by_id[chunk_id]
        if len(chunk) < 2:
            # Not useful.
            return
        raw_info = '\n'.join(chunk)
        time_now = datetime.datetime.utcnow().replace(microsecond=0)
        time_human = time_now.isoformat()
        time_created = time_now.timestamp()
        db.execute("INSERT INTO message (id, time_created, time_human, raw_info) VALUES "
            " (?,?,?,?)", (chunk_id, time_created, time_human, raw_info) )
        db.commit()
        db.close()
        # free memory:
        del self.chunks_by_id[chunk_id]

    def init_db(self):
        db = sqlite3.connect(self.db_filename)
        try:
            db.execute("CREATE TABLE message(id, time_created, time_human, raw_info, "
                " status, machine_id, session_id, lat, lon,"
                " PRIMARY KEY(id))")
            db.commit()
        except sqlite3.OperationalError:
            pass
        return db

class DynamicResolver(BaseResolver):

    possible_origins = (
        'example.test.',
        'mr8266.tk.'
        )

    def __init__(self):
        self.ttl = 120
        self.saver = DataSaver()

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
        self.saver.store_name(local_name)
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

