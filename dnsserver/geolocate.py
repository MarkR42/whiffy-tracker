#!/usr/bin/env python3

import os
import json
import sqlite3
import urllib.request

api_key = 'wrong'
MIN_ACCURACY = 200 # Metres

def load_api_key():
    global api_key
    api_key = open('api_key.txt').read().strip()

def normalise_mac(mac):
    # Convert mac adddress into 02:ab:cd:ef:09:10
    mac = mac.replace(':','')
    chunks = []
    for n in range(len(mac) // 2):
        chunk = mac[n*2: n*2 + 2]
        chunks.append(chunk.upper())
    return ':'.join(chunks)

def geolocate(ap_list):
    # Build json request
    jsonobj = {'wifiAccessPoints': [
       { "macAddress" : a[0], "signalStrength": a[1] } 
        for a in ap_list ] 
        }
    url = 'https://www.googleapis.com/geolocation/v1/geolocate?key=' + api_key
    req = urllib.request.Request(url, bytes(json.dumps(jsonobj), 'ascii'),
        headers = {'Content-Type': 'application/json'} )
    resp = urllib.request.urlopen(req)
    resp_json = str(resp.read(), 'ascii')
    print(resp_json)
    respobj = json.loads(resp_json)
    if 'location' in respobj:
        loc = respobj['location']
        if respobj['accuracy'] < MIN_ACCURACY:
            return (loc['lat'], loc['lng'])
    # Not found
    return None 

def process_message(db, id, raw_info):
    print("Processing message id=", id)
    entries = raw_info.split('\n')
    entset = set(map(lambda s: s.strip(), entries))
    aps = [] # List of tuple: macaddr, sig strength
    for entry in sorted(entset):
        bits = entry.split('-', 2)
        if bits[0] == 'ap':
            # Accesspoint
            mac = normalise_mac(bits[1])
            strength = int(bits[2])
            aps.append( (mac, strength) )
    for ap in aps:
        print(ap) 
    status = 'ERROR'
    lat = None
    if len(aps) > 1:
        # We can geolocate.
        where = geolocate(aps)
        if where is not None:
            lat, lon = where
            status = 'OK'
    with db:
        db.execute('UPDATE message SET status=? WHERE id=?',
            (status, id))
        if lat:
            db.execute('UPDATE message SET lat=?, lon=? WHERE id=?',
                (lat, lon, id))

def main():
    load_api_key()
    db = sqlite3.connect('messages.sqlite3')
    cur = db.cursor()
    cur.execute('select id, raw_info from message where status is null');
    for row in cur:
        id, raw_info = row
        process_message(db, id, raw_info)

if __name__ == '__main__':
    main()
