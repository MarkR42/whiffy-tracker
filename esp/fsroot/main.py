import wscan
import time
import network

def go():
    wscan.main()

def delayed_go():
    for i in range(15,0,-1):
        print("Will start main activity in %d seconds" % (i,))
        time.sleep(1)
    return go()

def myscan():
    for ap in sta_if.scan():
        print(ap)

delayed_go()
