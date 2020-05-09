import threading

class Command:
    CMD_STOP_REC            = 1
    CMD_START_REC           = 2
    CMD_REBOOT              = 3
    CMD_SHUTDOWN            = 4
    CMD_ROTATE              = 5
    CMD_SET_SYS_DATETIME    = 6
    
    def __init__(self, cmd, data=None):
        self.cmd = cmd
        self.data = data
        self._event = threading.Event()
        
    def done(self):
        self._event.set()

    def wait(self, timeout_seconds=5):
        return self._event.wait(timeout_seconds)
            
