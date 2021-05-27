import os, sys, inspect, time, errno, signal

def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)

def isnotebook():
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True   # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False      # Probably standard Python interpreter
    
ROOT_DIR    = f'{get_script_dir()}/../'
EMPTY_LIMIT = 4000 # max improvement value to assume the land is empty 

class FileLock(object):
    
    def __init__(self, file_name, timeout=10, delay=.05):
        if timeout is not None and delay is None:
            raise ValueError("If timeout is not None, then delay must not be None.")
        self.is_locked = False
        self.lockfile  = f'{file_name}.lock'
        self.file_name = file_name
        self.timeout   = timeout
        self.delay     = delay
 
 
    def acquire(self):
        start_time = time.time()
        while True:
            try:
                self.fd = os.open(self.lockfile, os.O_CREAT|os.O_EXCL|os.O_RDWR)
                self.is_locked = True
                break
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                if self.timeout is None or (time.time() - start_time) > self.timeout:
                    raise Exception(f'Could not acquire lock on {self.file_name}')
                time.sleep(self.delay) 
 
    def release(self):
        if self.is_locked:
            os.close(self.fd)
            os.unlink(self.lockfile)
            self.is_locked = False
 
    def __enter__(self):
        if not self.is_locked:
            self.acquire()
        return self
 
    def __exit__(self, type, value, traceback):
        if self.is_locked:
            self.release()
 
    def __del__(self):
        self.release()

class Timeout():
    class TimeoutException(Exception):
        pass

    def _timeout(signum, frame):
        raise Timeout.TimeoutException()

    def __init__(self, timeout=10):
        self.timeout = timeout
        signal.signal(signal.SIGALRM, Timeout._timeout)

    def __enter__(self):
        signal.alarm(self.timeout)

    def __exit__(self, exc_type, exc_value, traceback):
        signal.alarm(0)
        return exc_type is Timeout.TimeoutException
