#!/usr/bin/env python3

import os
import json
import sqlite3
import time
import datetime

def main():
    db = sqlite3.connect('messages.sqlite3')
    cur = db.cursor()
    now = datetime.datetime.now()
    midnight = datetime.datetime(now.year, now.month, now.day, 0,0,0)
    midnight_ts = midnight.timestamp()
    cur.execute("select id, time_created, lat, lon,time_human from message where status='OK' "
        " and time_created > ? order by time_created", (midnight_ts, ));
    with open('markers.js', 'w') as f:
        print("var markers=[", file=f)
        for row in cur:
            id, time_created, lat, lng, time_human = row
            print(" {lat: %f, lng: %f, id: '%s'}, " % (lat, lng, time_human), file=f )   
        print("];", file=f)

if __name__ == '__main__':
    main()
