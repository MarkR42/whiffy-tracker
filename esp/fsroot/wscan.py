import time
import os
import network
import socket
import machine
import ubinascii
import log
import telemetry
import sys

# Our lib:
import minihttp

TIME_HOST = 'time.' + telemetry.TELEMETRY_DOMAIN

blueled = None

def led_on():
    blueled.low()
    
def led_off():
    blueled.high()

def wait_for_ap_connected(sta_if):
    # Returns True if successful.
    for n in range(20):
        time.sleep_ms(500)
        st = sta_if.status()
        # Bail out early if we get NO_AP_FOUND.
        if st == network.STAT_NO_AP_FOUND:
            return False
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
        else:
            print("Failed to connect to ", ssid)
    # Nothing useful found, cancel any pending connection.
    sta_if.disconnect()
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

clock_is_set = False

def maybe_set_clock_from_dns():
    # Lookup time.mr8266.tk
    # Which gives us an IPv4 address which contains the number of
    # seconds since 2000
    # Check if clock is already set.
    global clock_is_set
    if clock_is_set:
        # Already set.
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
        if not 2016 <= lt[0] <= 2019:
            log.log("Implausible time, from dns server. Ignoring.")
            return
            
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
        clock_is_set = True

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
        telsession.send_telemetry()

def mainloop(sta_if):
    telsession = telemetry.TelemetrySession()
    # Now search for a valid API.
    while True:
        sta_if.disconnect()
        ok = search_for_ap(sta_if, telsession)
        if ok:
            investigate_dns(telsession)
        log.flush()    

def main():
    log.log("Starting main")
    log.log("machine.reset_cause = ", machine.reset_cause())
    global blueled
    blueled = machine.Pin(2, machine.Pin.OUT)
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
    sys.exit() # Soft reboot
    

