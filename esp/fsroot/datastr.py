"""
    Memory-efficient list of byte-strings.

"""

class RecentStrings(object):
    """
        Recent strings. Stores a kind of sloppy list of some bytestrings
        with the most recently added ones most likely to be found.
        
    """
    
    modified = False
    
    def __init__(self, size):
        self._bytes = bytearray(size)
        
    def add(self, bytestr):
        if bytestr in self: # No duplicate.
            return
        # Move everything along to make room.
        l = len(bytestr)
        l1 = l + 1
        
        self._bytes[l1:] = self._bytes[:-l1]
        
        # Now slap bytestr there.
        self._bytes[:l] = bytestr
        # And a null
        self._bytes[l] = 0
        self.modified = True
        
    def __contains__(self, bytestr):
        # True if bytestr has been added and not yet fallen off the end.
        l = len(bytestr)
        if self._bytes[l] == 0 and self._bytes[:l] == bytestr:
            return True
        needle = b'\0' + bytestr + b'\0'
        
        return needle in self._bytes
        
    def save(self, filename):
        with open(filename, 'wb') as f:
            f.write(self._bytes)
        self.modified = False
            
    def load(self, filename):
        with open(filename, 'rb') as f:
            self._bytes[::] = f.read(len(self._bytes))
        self.modified = False
        
        
