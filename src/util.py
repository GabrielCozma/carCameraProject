import subprocess
import glob
import os
import datetime
import logging
import struct
import traceback

logger = logging.getLogger(__name__)

def get_cpu_temperature():
    temps = subprocess.check_output(['vcgencmd', 
                    'measure_temp']).decode('utf-8')
    if 'temp=' in temps:
        temps = temps.strip()
        tempv = temps.split('=')[1]
        return float(tempv.split("'")[0])
    
    return 0.0


def delete_old_logs(log_dir, days_to_keep=2):
    # Delete log files older than days_to_keep
    td = datetime.timedelta(days=days_to_keep)
    d = datetime.datetime.today() - td
    
    log_files = glob.glob(log_dir + '/*.log')
    for log_file in log_files:
            if os.path.getmtime(log_file) < d.timestamp():
                os.remove(log_file)
                logger.warning("Removing old log file: %s", log_file)

def get_wlan_info():
    try:
        ssid = subprocess.check_output("iwgetid -r".split()).decode('utf-8').strip()
        cfg = subprocess.check_output("ifconfig wlan0".split()).decode('utf-8').strip()
        i = cfg.find("inet ")
        ip = ""
        if i >= 0:
            ip = cfg[i:].split()[1]
    except Exception as e:
        logger.error("Failed to get WiFi connection details: %s", e)
        ssid = "-"
        ip = "-"
    finally:
        return (ssid, ip)

def reboot():
    os.system("sudo reboot")
    
def shutdown():
    os.system("sudo poweroff")

def set_system_datetime(dtime):
    os.system('sudo date -s "' + dtime.strftime("%Y-%m-%d %H:%M:%S") + '"')   
    
