import os

HOME = os.getcwd()

RECORDS_LOCATION = HOME + "/records"

# Maximum duration of each video in seconds.
DURATION_SEC = 60

MAX_USED_DISK_SPACE_PERCENT = 90

# Video parameters. 
VIDEO_FPS = 30
HIGH_RES_VIDEO_WIDTH = 1920
HIGH_RES_VIDEO_HEIGHT = 1080
VIDEO_QUALITY = 23

# Alternate video resolution to drop temperature.
LOW_RES_VIDEO_WIDTH = 1280
LOW_RES_VIDEO_HEIGHT = 720

# Size of text that will appear on top of recorded video.
ANNOTATE_TEXT_SIZE = 20

# How many days to keep old log files
KEEP_OLD_LOGS_FOR_DAYS = 2

# Reduce resolution when temperature exceeds threshold.
TEMPERATURE_THRESHOLD_HIGH = 75.0
# Restore high resolution when temperature drops.
TEMPERATURE_THRESHOLD_NORMAL = 60.0

HTTP_SERVER_PORT_NUMBER = 8080

CFG_FILENAME = "cfg.json"
CFG_FILE = RECORDS_LOCATION + '/' + CFG_FILENAME

RECORD_FORMAT_EXTENSION = ".mp4"

def update_records_location(loc):
    global RECORDS_LOCATION
    global CFG_FILE
    
    RECORDS_LOCATION = loc
    CFG_FILE = RECORDS_LOCATION + '/' + CFG_FILENAME

