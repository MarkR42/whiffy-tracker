import time
import os
import network
import socket
import machine
import ubinascii
import log
import telemetry
import sys
import datastr

# Our lib:
import minihttp

TIME_HOST = 'time.' + telemetry.TELEMETRY_DOMAIN

SSIDS_FILE = 'ssids.bin'
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

def search_for_ap(sta_if, telsession, recentgoodssids):
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
    ssid_list = list(ssid_set)
    log.log("AP count=", len(ssid_list))
    del ssid_set
    give_up_time = time.time() + 30 
    # Try "priority" ones stored in recentgoodssids
    for goodness in (True, False):
        for ssid in ssid_list:
            if time.time() > give_up_time:
                log.log("Took too long trying to connect to all APs")
                break
            good = (ssid in recentgoodssids)
            if good == goodness: 
                sta_if.connect(ssid, '', False) # 3rd parameter = save config
                # Wait for connection...
                ok = wait_for_ap_connected(sta_if)
                if ok:
                    log.log("Connected to ", ssid)
                    dns_ok = investigate_dns(telsession)
                    if dns_ok:
                        recentgoodssids.add(ssid)
                        return True
                else:
                    log.log("Failed to connect to ", ssid)
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

# This set to True only if we have set the clock from the network
# since the last boot or reset. Not other clock sources, or RTC
# over a reboot. 
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
        set_clock_from_secs(secs)
        clock_is_set = True
        
def set_clock_from_secs(secs):
    lt = time.localtime(secs)
    if not 2016 <= lt[0] <= 2019:
        log.log("Implausible time. Ignoring.")
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
    
def set_clock_from_file():
    # Called at boot time, try to set the clock from a file.
    if time.time() > (3600 * 24 * 365):
        # Already set
        return
    
    def try_clock_file(filename):
        try:
            timestamp = int(open(filename, 'r').readline())
        except OSError:
            return False
        log.log("Setting clock from file", filename)
        set_clock_from_secs(timestamp)
        return True
    
    if not try_clock_file("last.tim"):
        try_clock_file("build.tim")

def save_clock():
    # Called sometimes in the main loop.
    with open('last.tim', 'w') as f:
        print(time.time(), file=f)

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
    return honest
    
def use_working_ap(telsession):
    # Ok, we've got a working DNS.
    maybe_set_clock_from_dns()
    telsession.send_telemetry()

def mainloop(sta_if):
    telsession = telemetry.TelemetrySession()
    recentgoodssids = datastr.RecentStrings(60)
    try:
        recentgoodssids.load(SSIDS_FILE)
    except OSError:
        pass # Unable to load ssids file, but that's ok,
        # maybe we haven't created it yet.
    # Now search for a valid API.
    last_clock_save_time = 0
    while True:
        sta_if.disconnect()
        ok = search_for_ap(sta_if, telsession, recentgoodssids)
        if ok:
            use_working_ap(telsession)
        log.flush()   
        if recentgoodssids.modified:
            recentgoodssids.save(SSIDS_FILE)
        if clock_is_set and ((time.time() - last_clock_save_time) > 120):
            save_clock()
            last_clock_save_time = time.time()

def main():
    log.log("Starting main")
    log.log("machine.reset_cause = ", machine.reset_cause())
    global blueled
    blueled = machine.Pin(2, machine.Pin.OUT)
    set_clock_from_file()
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
    

