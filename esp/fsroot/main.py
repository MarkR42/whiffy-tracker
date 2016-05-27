import wscan
import time
import network

sta_if = network.WLAN(network.STA_IF)

# wscan.main()

def go():
    wscan.main()

def delayed_go():
    for i in range(60,0,-1):
        print("Will start main activity in %d seconds" % (i,))
        time.sleep(1)
    return go()

def myscan():
    for ap in sta_if.scan():
        print(ap)

delayed_go()
