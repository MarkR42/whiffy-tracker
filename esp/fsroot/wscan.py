import time
import os
import network
import socket
import machine
import ubinascii
import log

# Our lib:
import minihttp

TELEMETRY_DOMAIN = 'mr8266.tk'
TIME_HOST = 'time.' + TELEMETRY_DOMAIN

blueled = machine.Pin(2, machine.Pin.OUT)

def led_on():
    blueled.low()
    
def led_off():
    blueled.high()

def wait_for_ap_connected(sta_if):
    # Returns True if successful.
    for n in range(14):
        time.sleep_ms(500)
        if sta_if.isconnected():
            return True
    # Give up.
    return False

def search_for_ap(sta_if, telsession):
    """
        Do scans and find a working AP we can connect to without
        a password :)
    """
    # Get a list of ssids
    ssid_set = set()
    scan = None
    try:
        led_off()
        scan = sta_if.scan()
        for ap in scan:
            # auth_mode is ap[4], a value 0 means open.
            if ap[4] == 0: # AUTH_OPEN
                ssid_set.add(ap[0])
        led_on()
    except Exception:
        log.log("Scan fail - could be MemoryError")
        led_on()
        time.sleep(5)
        return False
    telsession.store_scan(scan)
    del scan
    # Try them in turn,
    ssid_list = sorted(ssid_set)
    del ssid_set
    for ssid in ssid_list:
        sta_if.connect(ssid, '')
        # Wait for connection...
        ok = wait_for_ap_connected(sta_if)
        if ok:
            log.log("Connected to ", ssid)
            return True
    log.log("No good accesspoints found")
    return False

def get_ip(name):
    try:
        ai = socket.getaddrinfo(name, 80)
    except OSError:
        return None
    if len(ai)>0:
        return ai[0][-1][0]
    else:
        return None

def maybe_set_clock_from_dns():
    # Lookup time.mr8266.tk
    # Which gives us an IPv4 address which contains the number of
    # seconds since 2000
    # Check if clock is already set.
    lt = time.localtime()
    if lt[0] >= 2016:
        # Year ok? Already set.
        return
    time_ip = get_ip(TIME_HOST)
    if time_ip is not None:
        print("Setting clock...")
        bits = list(map(int, time_ip.split('.')))
        print(bits)
        secs = 0
        for n in bits:
            secs *= 256
            secs += n
        del bits
        lt = time.localtime(secs)
        print("Setting RTC...")
        rtc = machine.RTC()
        # Unfortunately this is 
        # year, month, day, weekday, hour, min, sec, msec
        # Note that setting weekday doesn't make sense, that's ignored.
        rtc.datetime(
            (lt[0], lt[1], lt[2], 0,
            lt[3], lt[4], lt[5], 0)
            ) 
        log.log("RTC is set.")

def hex_str(s):
    return str(ubinascii.hexlify(s), 'ascii')

class SendTimeout(Exception):
    pass

class TelemetrySession():
    
    def __init__(self):
        # Create unique session id.
        self.session_id = hex_str(os.urandom(4))
        self.last_scan = None
        self.last_scan_time = None
        self.chunk_id = 0
    
    def send_chunk(self):
        try:
            self.maybe_send_chunk()
        except SendTimeout:
            log.log("Timeout while sending telemetry")
        
    def maybe_send_chunk(self):
        self.chunk_id += 1
        t0 = time.ticks_ms()
        def send1(info):
            # info must be a valid dns name and not too long
            try:
                # Info, session id, chunk id, domain:
                # e.g. hello.01234567.0001.mr8266.tk
                dnsname = '%s.%s.%04x.%s' % (info, self.session_id, self.chunk_id, TELEMETRY_DOMAIN)
                socket.getaddrinfo(dnsname, 80)
            except OSError:
                pass # may fail, but we ignore.
            # Check for timeout
            timetaken = time.ticks_diff(t0, time.ticks_ms())
            if timetaken > 20000:
                raise SendTimeout()
        
        send1('machine-' + hex_str(machine.unique_id()))
        send1('time-%d' % self.last_scan_time)
        # Send the last scan, if possible.
        if self.last_scan is not None:
            for ap in self.last_scan:
                mac = hex_str(ap[0])
                # Strength is usually a negative integer.
                strength = str(ap[1])
                send1('ap-' + mac + '-' + strength)
        # Send an "end of message"
        send1('eom')
        log.log("telemetry sent")
    
    def store_scan(self, scan):
        # Store the important parts of a scan result somewhere.
        # Scan is a tuple of tuples,
        # (ssid, macaddr, channel, strength, auth_mode, is_hidden)
        # Example:
        # (b'BTWifi-with-FON', b'Z\xd3\xf7f\xcd\x97', 6, -77, 0, 0)
        # We are only really interested in macaddr and signal strength.
        self.last_scan = [
            (s[1], s[3]) for s in scan
            ]
        self.last_scan_time = time.time()

def investigate_dns(telsession):
    print("Starting DNS investigation")
    def dns_is_honest():
        ip1 = get_ip('www.vectrex.org.uk')
        if ip1 is None:
            return False
        ip2 = get_ip('red.vectrex.org.uk')
        return (ip1 != ip2)
    
    honest = dns_is_honest()
    print("dns_is_honest: ", honest)
    # If DNS is not honest, try a http request to try to trigger a
    # dial-up or something...
    if not honest:
        try:
            junk = minihttp.get('http://www.example.com/')
        except OSError:
            print("http failed")
        # Now check again
        honest = dns_is_honest()
    print("dns_is_honest2: ", honest)
    if honest:
        # Ok, we've got a working DNS.
        maybe_set_clock_from_dns()
        telsession.send_chunk()

def mainloop(sta_if):
    telsession = TelemetrySession()
    # Now search for a valid API.
    while True:
        ok = search_for_ap(sta_if, telsession)
        if ok:
            investigate_dns(telsession)
        log.flush()
    

def main():
    log.log("Starting main")
    # If there is a AP active, let's turn it off.
    network.WLAN(network.AP_IF).active(False)
    # Now activate the STA interface.
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    log.log("Interfaces active")
    # In case we are already connected, disconnect.
    sta_if.disconnect()
    try:
        mainloop(sta_if)
    except Exception as e:
        log.log("Unexpected exception:", e)
    log.log("Bye bye")
    log.flush()
    time.sleep(10)
    machine.reset()
    

