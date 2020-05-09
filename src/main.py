# Entry point module for the program

import time
from datetime import datetime
import os
import sys
import logging
import util
import argparse
import queue
import traceback

import webinterface
import recorder
from command import Command
import config

# Log file location
LOG_FILE_PATH = (config.RECORDS_LOCATION 
                + '/' 
                + datetime.now().strftime("%Y-%m-%d")
                + '.log')
                
loglevel = logging.INFO

logging.basicConfig(format='%(module)s:%(lineno)s:%(levelname)s:%(message)s', 
        filename=LOG_FILE_PATH, 
        level=loglevel)

logger = logging.getLogger(__name__)

try:
        
    logger.info("Deleting logs older than {} days.".format(config.KEEP_OLD_LOGS_FOR_DAYS))
    util.delete_old_logs(config.RECORDS_LOCATION, config.KEEP_OLD_LOGS_FOR_DAYS)

    # Global command queue
    cmd_q = queue.Queue()


    recorder.init()
    logger.info("Starting Recording\n\n")
    recorder.start()

    webinterface.WebInterfaceHandler.cmd_q = cmd_q

    logger.info("Starting Web Server\n\n")
    web_th = webinterface.start()


    while True:
        request = cmd_q.get()
        if request.cmd == Command.CMD_REBOOT:
            recorder.stop()
            util.reboot()
            request.done()
        elif request.cmd == Command.CMD_SHUTDOWN:
            recorder.stop()
            util.shutdown()
            request.done()
        elif request.cmd == Command.CMD_STOP_REC:
            recorder.stop()
            request.done()
        elif request.cmd == Command.CMD_START_REC:
            recorder.start()
            request.done()
        elif request.cmd == Command.CMD_ROTATE:
            recorder.queue_commands(request)
        elif request.cmd == Command.CMD_SET_SYS_DATETIME:
            util.set_system_datetime(request.data)
            request.done()

except Exception as e:
    logger.error(e)
    logger.error(traceback.format_exc())
finally:
    recorder.stop()
    web_th.join()

