import socket

def get(url, max_redirects=1):
    # Get the contents of a URL, with redirects,
    # and return the first bit as a binary chunk
    # (subject to max length because of memory limit)
    # Taken from example here:
    # http://docs.micropython.org/en/latest/esp8266/esp8266/tutorial/network_tcp.html
    _, _, host, path = url.split('/', 3)
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()
    s.connect(addr)
    s.send(bytes('GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
    data = s.recv(512) # Assume this includes all the http header.
    # Find http status.
    space1 = data.index(b' ')
    space2 = data.index(b' ', space1+1)
    status_bytes = data[space1+1 : space2]
    http_status = int(status_bytes)
    print("HTTP STATUS:", http_status)
    # Check for redirect...
    is_redirect = (300 <= http_status <= 399)
    redirect_location = None
    # Parse headers, look for "location"
    linestart = data.index(b'\n') + 1
    while True:
        lineend = data.index(b'\n', linestart)
        if (lineend - linestart) < 3:
            # Short line: end of headers.
            break
        try:
            colonpos = data.index(b':', linestart, lineend)
            hdrname = str(data[linestart:colonpos], 'ascii').lower()
            # print("HDR:", hdrname)
            if hdrname == 'location':
                redirect_location = str(data[colonpos+1:lineend], 'ascii').strip()
        except ValueError:
            # No : found.
            break
        linestart = lineend + 1
    if is_redirect and redirect_location is not None:
        print("REDIRECT TO: " + redirect_location)
    # lineend should now point to start of content.
    #
    data = data[lineend + 1:]
    # We could read the rest of the response here.
    s.close()
    return data    
    
    
