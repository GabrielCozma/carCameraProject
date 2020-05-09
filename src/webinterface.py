from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from socketserver import ThreadingMixIn
import cgi
import os
from datetime import timedelta
from datetime import datetime
import traceback
import urllib.parse as url_parse
import threading
import subprocess
import time
import glob
import pathlib
import shutil
import logging
import io

from command import Command
import util
import recorder
import config

logger = logging.getLogger(__name__)

_SERVER_ADDRESS = ('', config.HTTP_SERVER_PORT_NUMBER)

_MINUTE_SEC = 60
_HOUR_SEC = 60 * _MINUTE_SEC


_HTTP_STATUS_CODE_BAD_REQUEST = 400
_HTTP_STATUS_CODE_REQUEST_TIMEOUT = 408
_HTTP_STATUS_CODE_NOT_FOUND = 404
_HTTP_STATUS_CODE_INTERNAL_SERVER_ERROR = 500
_HTTP_STATUS_CODE_RANGE_NOT_SATISFIABLE= 416

_HTTP_STATUS_CODE_OK = 200
_HTTP_STATUS_CODE_REDIRECT = 302
_HTTP_STATUS_CODE_PARTIAL_CONTENT = 206


class WebInterfaceHandler(BaseHTTPRequestHandler):
    program_start_time = None
    
    cmd_q = None
    
    def do_GET(self):
        try:
            self.protocol_version = "HTTP/1.1"
            logger.debug("\nPath: %s", self.path)
            for header, value in self.headers.items():
                logger.debug("%s: %s", header, value)
            if self.path == '/':
                self.serve_index()
            elif self.path == '/reboot':
                self.redirect_to_home()
                command = Command(Command.CMD_REBOOT)
                WebInterfaceHandler.cmd_q.put(command)
            elif self.path == '/poweroff':
                self.redirect_to_home()
                command = Command(Command.CMD_SHUTDOWN)
                WebInterfaceHandler.cmd_q.put(command)
            elif '/get-record' in self.path:
                kv = self.parse_get_params()
                if 'f' in kv:
                    self.serve_record(kv['f'][0], True)        
                else:
                    self.send_error(_HTTP_STATUS_CODE_BAD_REQUEST)
            elif '/play-record' in self.path:
                kv = self.parse_get_params()
                if 'f' in kv:
                    self.serve_record(kv['f'][0], False)        
                else:
                    self.send_error(_HTTP_STATUS_CODE_BAD_REQUEST)
            elif self.path == '/stop':
                command = Command(Command.CMD_STOP_REC)
                WebInterfaceHandler.cmd_q.put(command)
                if command.wait():
                    self.redirect_to_home()
                else:
                    self.send_error(_HTTP_STATUS_CODE_REQUEST_TIMEOUT)
            elif self.path == '/start':
                command = Command(Command.CMD_START_REC)
                WebInterfaceHandler.cmd_q.put(command)
                if command.wait():
                    self.redirect_to_home()
                else:
                    self.send_error(_HTTP_STATUS_CODE_REQUEST_TIMEOUT)
            elif self.path.endswith(config.RECORD_FORMAT_EXTENSION):
                self.serve_record(self.path.lstrip("/"), False)
            else:
                msg = "Requested URI: '" + self.path + "' not found."
                self.send_error(_HTTP_STATUS_CODE_NOT_FOUND, explain=msg)
            return
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(e)
                        
    def parse_get_params(self):
        query = url_parse.urlsplit(self.path).query
        params = url_parse.parse_qs(query)
        return dict(params)
            
    def serve_index(self):
        self.home_page()
    
    def redirect_to_home(self):
        self.send_response(_HTTP_STATUS_CODE_REDIRECT) 
        self.send_header('Location', '/')
        
        self.end_headers()
        self.flush_headers()
            
    def serve_record(self, recname, download_play):
        # Either send the record file as attachment for download 
        # (download_play == true) or as
        # content (download_play == false)
        filepath = config.RECORDS_LOCATION + '/' + recname
        
        if os.path.exists(filepath) == False:
            self.send_error(_HTTP_STATUS_CODE_NOT_FOUND)
            return
        
        # Handle file opening error early, if file's recording is in
        # progress then reading it will cause lock error.
        try:
            with open(filepath, 'rb') as fileobj:
                try:
                    file_len = os.path.getsize(filepath)
                    
                    range_len = file_len
                    # Handle range request for iOS/Safari browser
                    if 'Range' in self.headers.keys():
                        logger.debug("Handling range request: %s", 
                                self.headers['Range'])
                        ok, fpos, lpos, rlen = self.get_range (
                                        self.headers['Range'],
                                        file_len)
                        if not ok:
                            self.send_error(
                                _HTTP_STATUS_CODE_RANGE_NOT_SATISFIABLE)                   
                            return
                        
                        logger.debug("Sending range: %s-%s, length: %s", 
                                fpos, lpos, rlen)
                                
                        self.send_response(
                            _HTTP_STATUS_CODE_PARTIAL_CONTENT)
                        self.send_header('Content-Length', 
                                str(rlen))
                        self.send_header('Content-Range', 
                                "bytes {0}-{1}/{2}".format(
                                fpos, lpos, file_len))
                        fileobj.seek(fpos)
                        range_len = rlen
                    else:
                        self.send_response(_HTTP_STATUS_CODE_OK)
                        self.send_header('Content-Length', 
                                        str(file_len))
        
                    if download_play: #download as file
                        self.send_header('Content-type','application/octet-stream')
                        self.send_header('Content-Disposition', 
                                        "attachment;filename=" + recname)
                    else: #play
                        self.send_header('Content-type','video/mp4')
                                    
                    self.end_headers()
                    
                    try:
                        if range_len < file_len:
                            self.send_file_range(fileobj, range_len)
                        else:
                            shutil.copyfileobj(fileobj, self.wfile)
                    except ConnectionResetError as e:
                        logger.warning(e)
                    except BrokenPipeError as e:
                        logger.warning(e)
                except Exception as e:
                    logger.error(e)
        except Exception as e:
            self.send_error(_HTTP_STATUS_CODE_INTERNAL_SERVER_ERROR,
                        explain=str(e))
            return
        
    def send_file_range(self, fileobj, length):
        # file is already seeked
        # copy in chunks 
        
        bs = length
        if length > io.DEFAULT_BUFFER_SIZE:
            bs = io.DEFAULT_BUFFER_SIZE
        
        total_bytes_copied = 0
        while total_bytes_copied < length:
            # read is buffered: len(d) == bs
            if bs >= (length - total_bytes_copied):
                d = fileobj.read(bs)
            else:
                d = fileobj.read(length - total_bytes_copied)
                
            if len(d) == 0:
                break
            self.write_to_connection(d)
            total_bytes_copied += bs
        
    def write_to_connection(self, data):
        # writing to socket may write less data
    
        total_bytes_written = 0
        while total_bytes_written < len(data):
            bytes_written = self.wfile.write(data[total_bytes_written:])
            if bytes_written == 0:
                break
            total_bytes_written += bytes_written
        
    def get_range(self, spec, content_length):
        # common range format: bytes=a-b,c-d,...
        # return tuple: (success, first position, last position, 
        # range length)
        err = (False, 0, 0, 0)
        
        if "bytes=" not in spec:
            return err
        
        try:    
            # for now support only one/first range spec.
            first_range = spec.split(',')[0]
            r = first_range.split('=')[1]
            pos = r.split('-')
            
            fpos = 0
            lpos = content_length - 1
            
            if pos[0] == '':
                # sufix mode
                length = int(pos[1])
                fpos = content_length - length - 1
            elif pos[1] == '':
                # remaining mode
                fpos = int(pos[0])
            else:
                fpos = int(pos[0])
                lpos = int(pos[1])
            
            # Validate 
            if fpos > lpos:
                return err
            if lpos >= content_length:
                return err
            if fpos < 0:
                return err
            if lpos < 0:
                return err
            
            return (True, fpos, lpos, lpos-fpos+1)    
                    
        except Exception as e:
            logger.error(e)                
            return err
        
    def home_page(self):
        self.send_response(_HTTP_STATUS_CODE_OK)
        self.send_header('Content-type','text/html')
        
        filepath = config.HOME + '/html/home.html'
        
        page = ''
        with open(filepath, 'r') as f:
                page = f.read()
        
        # Update SoC temperature

        cpu_temp = util.get_cpu_temperature()
        page = page.replace('_STEMP', str(cpu_temp) + "&deg;C")
        page = page.replace('_STEMP_NORMAL', str(config.TEMPERATURE_THRESHOLD_NORMAL) + "&deg;C")
        page = page.replace('_STEMP_HIGH', str(config.TEMPERATURE_THRESHOLD_HIGH) + "&deg;C")
        
        # Caluclate program uptime not system.
        duration = datetime.now() - WebInterfaceHandler.program_start_time
        total_secs = int(duration.seconds)
        uptime = ''
        if total_secs >= _HOUR_SEC:
            hours = int(total_secs / _HOUR_SEC)
            total_secs = total_secs % _HOUR_SEC
            uptime += "{0} hours ".format(hours)
        if total_secs > _MINUTE_SEC:
            mins = int(total_secs / _MINUTE_SEC)
            total_secs = total_secs % _MINUTE_SEC
            uptime += "{0} mins ".format(mins)
        uptime += "{0} seconds ".format(total_secs)
        page = page.replace('_UPTIME', uptime)
        
        ssid, my_ip = util.get_wlan_info()
        page = page.replace('_WLAN_SSID', ssid)
        page = page.replace('_IP_ADDR', my_ip)
        disk_space_used_percent = recorder.get_disk_space_info()
        page = page.replace('_DISK_SPACE', 
            str(disk_space_used_percent) + '%')
        page = page.replace('_N_LOOPS',
            str(recorder.n_loops))
        page = page.replace('_CURR_REC',
            str(recorder.current_record_name))
        
        if recorder.recording_on:
            page = page.replace('_STATUS_COLOR', "lightgreen")
        else:
            page = page.replace('_STATUS_COLOR', "orange")
        
        rec_control = '<a href="/start">Start Recording</a>'
        if recorder.recording_on:
            rec_control = '<a href="/stop">Stop Recording</a>'

        page = page.replace('_REC_CONTROL', rec_control)

        rec_table_rows = ''
        serial_no = 0;
        rec_files = glob.glob(config.RECORDS_LOCATION + '/*' 
                        + config.RECORD_FORMAT_EXTENSION)
        rec_files.sort(key=os.path.getmtime, reverse=True)
        
        for record in rec_files:
            rec_filename = pathlib.Path(record).name
            serial_no += 1
            rec_table_rows += """
                     <tr>
                            <td>{0}</td>
                            <td><a href="get-record?f={1}">{2}</a></td>
                            <td><button class="pbutton" 
                                title="Play Record" 
                                onclick='play_rec("{3}");'>
                                &#9658;</button></td>
                     </tr>
                    """.format(serial_no, rec_filename, 
                                rec_filename, rec_filename)

        page = page.replace('_REC_TABLE_ROWS', rec_table_rows)
        

        self.send_header('Content-Length', str(len(page)))
        self.send_no_cache()
        self.end_headers()
        
        self.wfile.write(bytes(page, "utf8"))
    
    def send_no_cache(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Expires', '0')
        
class ThreadingWebServer(ThreadingMixIn, HTTPServer):
    # Make each request handler run in its own thread.
    # Improves browser performance and user experience.
    pass
            
def _start_webserver():
    WebInterfaceHandler.program_start_time = datetime.now()
    server = ThreadingWebServer(_SERVER_ADDRESS, WebInterfaceHandler)
    server.serve_forever()

def start():
    # called from main module
    th = threading.Thread(target=_start_webserver)
    th.daemon = True
    th.start()
    return th
               
if __name__ == "__main__":
    # For testing in standalone mode.
    try:
        _start_webserver()
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(e)
