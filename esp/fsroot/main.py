import time
import network
import machine

def go():
    import wscan
    wscan.main()

def delayed_go():
    if machine.reset_cause() == 2:
        # Crash?
        # Go immediately
        return go()
        
    for i in range(15,0,-1):
        print("Will start main activity in %d seconds" % (i,))
        time.sleep(1)
    return go()

def myscan():
    for ap in sta_if.scan():
        print(ap)

delayed_go()

# import miniserver
# miniserver.start_server()
