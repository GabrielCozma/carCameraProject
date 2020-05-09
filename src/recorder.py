import time
import picamera
from datetime import datetime
import json
import os
import subprocess
import glob
import sys
import logging
import util
import threading
import queue
import traceback

import mp4writer
from command import Command
import config

logger = logging.getLogger(__name__)

CFG_ROT_KEY = 'rotation'

CFG_CURR_INDEX_KEY = 'cindex'

CFG_MAX_FILES_KEY = 'max-files'

CFG_N_LOOPS_KEY = 'n-loops'

# Dictionary to save configuration settings.
_cfg = { 
    CFG_ROT_KEY: 0,
    CFG_CURR_INDEX_KEY: 0,
    CFG_MAX_FILES_KEY:0,
    CFG_N_LOOPS_KEY: 0
}

KB = 1024
MB = KB * KB

current_record_name = ""
last_recorded_name = "PLEASE WAIT"
n_loops = 0
recording_on = False
recording_status_text = ""

_VIDEO_WIDTH = config.HIGH_RES_VIDEO_WIDTH
_VIDEO_HEIGHT = config.HIGH_RES_VIDEO_HEIGHT

_th_recorder = None
_stop = True
_cmd_q = queue.Queue()


def _cfg_save():
    global _cfg
    with open(config.CFG_FILE, 'w') as f:
        json.dump(_cfg, f)

        
def get_disk_space_info():
    params = None
    try:
        op = subprocess.check_output(['df',
                        config.RECORDS_LOCATION]).decode('utf-8').split('\n')
        params = op[1].split()                
        params[4] = int(params[4].strip('%'))
        return params[4]
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        return None


def init():
    global _cfg  
    # Load existing configuration file or start fresh.
    if os.path.exists(config.CFG_FILE):
        with open(config.CFG_FILE, 'r') as f:
            _cfg = json.load(f)

def start():
    global _th_recorder
    global _stop
    
    if _stop:
        _th_recorder = threading.Thread(target=_loop_recoder)
        _stop = False
        _th_recorder.start()
    
def stop():
    global _th_recorder
    global _stop
    if _th_recorder:
        _stop = True
        _th_recorder.join()
        
def queue_commands(request):
    _cmd_q.put(request)

def _build_timestamp(forfile=True):
    if forfile:
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S") 
    else:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S") 

def _loop_recoder():
    global _cfg
    global _stop
    global _VIDEO_WIDTH
    global _VIDEO_HEIGHT
    global n_loops
    global current_record_name
    global last_recorded_name
    global recording_on
    
    try:
        camera = None
        logger.info("Initializing Pi Camera to {0}x{1} @ {2} fps".format(
                    _VIDEO_WIDTH, _VIDEO_HEIGHT, config.VIDEO_FPS)
        
        # Initialize camera
        camera = picamera.PiCamera()
        camera.resolution = (_VIDEO_WIDTH, _VIDEO_HEIGHT)
        camera.framerate_range = (1, config.VIDEO_FPS)
        camera.framerate = config.VIDEO_FPS
        camera.annotate_background = True
        camera.annotate_text_size = config.ANNOTATE_TEXT_SIZE
        current_rotation = _cfg[CFG_ROT_KEY]
        camera.rotation = current_rotation
    
        location_text = None
    
        index = _cfg[CFG_CURR_INDEX_KEY] + 1
        n_loops = _cfg[CFG_N_LOOPS_KEY]
        
        high_temp_triggered = False
        
        recording_on = True
    
        while not _stop:
            try:        
                disk_used_space_percent = get_disk_space_info()
                    
                if _cfg[CFG_MAX_FILES_KEY] == 0:
                    if (disk_used_space_percent >=  config.MAX_USED_DISK_SPACE_PERCENT):
                    _cfg[CFG_MAX_FILES_KEY] = index
                        index = 0
                        n_loops += 1
                        _cfg[CFG_N_LOOPS_KEY] = n_loops
                elif index >= _cfg[CFG_MAX_FILES_KEY]:
                    index = 0
                    n_loops += 1
                    _cfg[CFG_N_LOOPS_KEY] = n_loops
                        
                # Update SoC temperature in video annotation, to keep 
                # track of resolution drop vs temp.
                cpu_temp = util.get_cpu_temperature()
                if cpu_temp >= config.TEMPERATURE_THRESHOLD_HIGH:
                    if not high_temp_triggered:
                        logger.warning("CPU temperature %s C exceeded threshold %s C",
                                        cpu_temp, config.TEMPERATURE_THRESHOLD_HIGH)
                        logger.warning("Reducing video resolution")
                        _VIDEO_WIDTH = config.LOW_RES_VIDEO_WIDTH
                        _VIDEO_HEIGHT = config.LOW_RES_VIDEO_HEIGHT
                        camera.resolution = (_VIDEO_WIDTH, _VIDEO_HEIGHT)
                        high_temp_triggered = True
                elif cpu_temp <= config.TEMPERATURE_THRESHOLD_NORMAL:
                    if high_temp_triggered:
                        logger.warning("Restoring high video resolution")
                        _VIDEO_WIDTH = config.HIGH_RES_VIDEO_WIDTH
                        _VIDEO_HEIGHT = config.HIGH_RES_VIDEO_HEIGHT
                        camera.resolution = (_VIDEO_WIDTH, _VIDEO_HEIGHT)
                        high_temp_triggered = False
                        
                _update_subs_on_cpu_temp(cpu_temp)
                        
                # Record file name format: index_yyyy-mm-dd_HH-MM-SS.mp4
                rec_index = str(index)
                rec_time = _build_timestamp(forfile=False)
                rec_filename =  (rec_index 
                                +  '_' 
                                + _build_timestamp()
                                + config.RECORD_FORMAT_EXTENSION)
                rec_filepath = config.RECORDS_LOCATION + '/' + rec_filename
                
                video_format_text = "RPi DashCam {0}x{1} @ {2}fps".format(
                                        _VIDEO_WIDTH,
                                        _VIDEO_HEIGHT,
                                        config.VIDEO_FPS)
                
                _cfg[CFG_CURR_INDEX_KEY] = index
                _cfg_save()
                 
                existing_records = glob.glob(config.RECORDS_LOCATION 
                                    + '/' 
                                    + rec_index +  '_*')
                for record in existing_records:
                    os.remove(record)
                        
                mp4wfile = mp4writer.MP4Writer(filepath=rec_filepath,
                                fps=config.VIDEO_FPS)
                
                camera.start_recording(mp4wfile, format='h264',
                                quality=config.VIDEO_QUALITY)
                
                current_record_name = rec_filename
                                
                seconds = 0 
                while (not _stop) and (seconds < config.DURATION_SEC):
                    # update time
                    rec_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    camera.annotate_text = (rec_index 
                                            + ' - ' 
                                            + rec_time 
                                            + ' - ' 
                                            + 'T ' + str(cpu_temp) + 'C - '
                                            + video_format_text
                                            + ' - '
                                            + fixed_annotation)
                    
                    if location_text:
                        camera.annotate_text += '\n' + location_text
                    # poll for any recorder related commands
                    try:
                        request = _cmd_q.get(block=False)
                        if request.cmd == Command.CMD_ROTATE:
                            current_rotation += 90
                            if current_rotation >= 360:
                                current_rotation = 0
                            camera.rotation = current_rotation
                            _cfg[CFG_ROT_KEY] = current_rotation
                            _cfg_save()
                            request.done()
                    except queue.Empty:
                        pass
                    
                    camera.wait_recording(1)
                    seconds += 1
                    
                camera.stop_recording()
                
                mp4wfile.close()
                
                last_recorded_name = rec_filename
                
                index += 1
                
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error(e)        
                logger.error('Recording Stopped')
                break
        
        recording_on = False
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(e)        
    finally:
        if camera:
            camera.close()
