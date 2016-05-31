#
# Very simple logging.

# Write to a log file, with the date in filename.
# write timestamps into the file.

import time

_log_filename = None
_log_file = None

def log(*msg):
    global _log_filename, _log_file
    # create a log filename based on the current time.
    now = time.localtime()
    new_fn = '%04d%02d%02d.log' % (now[0], now[1], now[2])
    if new_fn != _log_filename:
        if _log_file:
            _log_file.close()
        _log_filename = new_fn
        _log_file = open(new_fn, 'a')
    timestr = '%02d:%02d:%02d' % (now[3], now[4], now[5])
    print(timestr, *msg, file=_log_file)
    # Also write to stdout.
    print(timestr, *msg)
    
def flush():
    if _log_file:
        _log_file.flush()
    
