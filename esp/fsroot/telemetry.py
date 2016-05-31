import log
import machine
import socket
import time
import os
import ubinascii

TELEMETRY_DOMAIN = 'mr8266.tk'
# Minimum time between chunks:
MIN_STORE_TIME = 30 # Seconds

DATA_FILE_NAME = 'telem.dat'
def hex_str(s):
    return str(ubinascii.hexlify(s), 'ascii')

class SendTimeout(Exception):
    pass

"""
    Position data are stored in telem.dat data file, as a sequence
    of lines in (binary) ascii which we will send to our DNS server
    whenever possible.
    
    On successful transmission, we move self.file_read_pos on.
    
    If we reach the end of the file, i.e. we're up to date, we
    can truncate the file to save temp space.
"""

class TelemetrySession():
    
    def __init__(self):
        # Create unique session id.
        self.session_id = hex_str(os.urandom(4))
        self.last_scan_time = 0
        self.chunk_id = 0
        # data_file is to be used to store telemetry temporarily.
        self.data_file = open(DATA_FILE_NAME, 'a+b')
        # file_read_pos is where we've reached in data_file, sending
        # successfully.
        self.file_read_pos = 0
    
    def store_scan(self, scan):
        # Check if we already did a scan too recently.
        now = time.time()
        if (now - self.last_scan_time) < MIN_STORE_TIME:
            # Nothing to do.
            return
        self.last_scan_time = now

        # Seek to end of file
        self.data_file.seek(0,2)
        
        def store_info(info):
            # Store binary info.
            self.data_file.write(info)
            self.data_file.write(b"\n")
            
        store_info(b'machine-' + hex_str(machine.unique_id()))
        store_info(b'time-%d' % (now, ))
        for s in scan:
            bssid = s[1]
            strength = s[3]
            store_info(b'ap-%s-%d' % (hex_str(bssid), strength))
        store_info(b'eom')
        # Make sure data are written.
        self.data_file.flush()
        
    def send_telemetry(self):
        """
            Send any pending telemetry.
            
            This is called when we think we are connected to a working
            accesspoint (although it may fail anyway)
            
            Each line in the data file needs to have chunk_id and session_id appended,
            when sent.
            
            After we successfully send a chunk we should increment chunk id
            so that the next chunk gets a new chunk id, not duplicate.
            
            If we successfully send some data, we should move 
            self.file_read_pos so that we don't repeat it.
            
            If we reach the end of the file, we should truncate the file.
        """
        def try_to_send(info):
            dnsname = b'%s.%s.%04x.%s' % (info, self.session_id, self.chunk_id, TELEMETRY_DOMAIN)
            try:
                socket.getaddrinfo(dnsname, 80)
                return True
            except OSError:
                return False
            
        
        # Seek to end of file
        self.data_file.seek(0,2)
        eof_pos = self.data_file.tell()
        if eof_pos == self.file_read_pos:
            # Nothing to do
            return
        
        #Seek to the reading position
        self.data_file.seek(self.file_read_pos)
        while self.file_read_pos < eof_pos:
            line = self.data_file.readline()
            if try_to_send(line.rstrip()):
                # Success
                self.file_read_pos = self.data_file.tell()
                if line.startswith(b'eom'):
                    self.chunk_id += 1
            else:
                # Fail
                return
        self.truncate_datafile()
        # If we get here, all telemetry is sent!
        log.log("telemetry sent, next chunk_id=%d" % (self.chunk_id,))
        
    def truncate_datafile(self):
        # Truncate file.
        # There is no file.truncate(),
        self.data_file.close()
        # Open it in a mode which will truncate.
        self.data_file = open(DATA_FILE_NAME, 'w+b')
        self.file_read_pos = 0
        
