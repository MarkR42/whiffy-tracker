import log
import machine
import socket
import time
import os
import ubinascii

TELEMETRY_DOMAIN = 'mr8266.tk'
# Minimum time between chunks:
MIN_STORE_TIME = 20 # Seconds

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
    
    If the device crashes, then we will reset file_read_pos to zero
    on the next restart, and (possibly) resend a whole load of 
    telemetry, which should be ignored so it's ok.
"""

class TelemetrySession():
    
    session_id = None
    chunk_id = 0
    reset = True
    
    def __init__(self):
        
        self._init_from_rtcmemory()
        if not self.session_id:
            # Create probably unique session id.
            self.session_id = hex_str(os.urandom(4))
        self.last_scan_time = 0
        # data_file is to be used to store telemetry temporarily.
        self.data_file = open(DATA_FILE_NAME, 'a+b')
        # file_read_pos is where we've reached in data_file, sending
        # successfully.
        self.file_read_pos = 0
        
    def _init_from_rtcmemory(self):
        # Check rtc memory
        rtc = machine.RTC()
        rtcmem = rtc.memory()
        if len(rtcmem) == 0:
            return
        # rtc memory should contain session_id,chunk_id
        bits = rtcmem.split(b',')
        if len(bits) == 2:
            # Ok
            self.session_id = bits[0]
            self.chunk_id = int(bits[1])
            log.log("Using previous session id from rtcmemory:" , self.session_id)
    
    def _save_to_rtcmemory(self):
        rtc = machine.RTC()
        rtc.memory(b'%s,%d' % (self.session_id, self.chunk_id))
    
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
        if self.reset:
            store_info(b'reset-%d' % (machine.reset_cause()))
            self.reset = False
            
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
                r = socket.getaddrinfo(dnsname, 80)
                ipv4addr = r[0][-1][0]
                if not ipv4addr.startswith(b'127.0.0.'):
                    log.log("bad telemetry response:", ipv4addr)
                    return False
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
            current_pos = self.data_file.tell()
            # If this is the very LAST item,
            if current_pos == eof_pos:
                # Send an extra element "tx" to indicate that
                # this is a transmit chunk.
                # This will be sent just before the final "eom" in
                # a batch.
                try_to_send(b"tx") # NB: This can fail, it's ok.
            if try_to_send(line.rstrip()):
                # Success
                self.file_read_pos = self.data_file.tell()
                if line.startswith(b'eom'):
                    self.chunk_id += 1
            else:
                # Fail - we will retry because file_read_pos has not
                # been moved.
                return
        self.truncate_datafile()
        # If we get here, all telemetry is sent!
        log.log("telemetry sent, next chunk_id=%d" % (self.chunk_id,))
        self._save_to_rtcmemory()
        
    def truncate_datafile(self):
        # Truncate file.
        # There is no file.truncate(),
        self.data_file.close()
        # Open it in a mode which will truncate.
        self.data_file = open(DATA_FILE_NAME, 'w+b')
        self.file_read_pos = 0
        
