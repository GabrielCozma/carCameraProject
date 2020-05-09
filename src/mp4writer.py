import subprocess
import threading
import queue
import traceback
import logging
import io
import shutil

logger = logging.getLogger(__name__)

class MP4Writer:
    MAX_QUEUE_SIZE = 50
    # Video buffer size to hold before commiting to queue.
    MAX_VIDEO_BIO_SIZE = 1*1024*1024
    
    def __init__(self, filepath="o.mp4", fps=30, 
                input_format="h264", codec="copy"):
        self._filepath = filepath
        self._fps = fps
        self._iformat = input_format
        self._codec = codec
        
        ffmpeg_cmd = """ffmpeg -v 16 -framerate {0} -f {1}
                    -i pipe:0 -codec {2} -movflags faststart
                    -y -f mp4 {3}""".format(
                        self._fps,
                        self._iformat,
                        self._codec,
                        self._filepath)
        
        self._proc = subprocess.Popen(ffmpeg_cmd.split(), 
                                stdin=subprocess.PIPE)
                                
        self._video_q = queue.Queue(MP4Writer.MAX_QUEUE_SIZE)
        self._video_bio_size = 0
        self._video_bio = io.BytesIO()
        
        self._th = threading.Thread(target=self.write_to_proc)
        self._th.daemon = True
        self._th.start()
        
    def write(self, vdata):        
        self._video_bio.write(vdata)
        self._video_bio_size += len(vdata)
        
        if self._video_bio_size >= MP4Writer.MAX_VIDEO_BIO_SIZE:
            self._video_q.put(self._video_bio)
            self._video_bio = io.BytesIO()
            self._video_bio_size = 0
            
    def flush(self):
        if self._video_bio_size > 0:
            self._video_q.put(self._video_bio)
            self._video_bio = io.BytesIO()
            self._video_bio_size = 0
            
    def get_file_object(self):
        return self._proc.stdin
            
    def close(self):
        self.flush()
        self._video_bio.close()
        self._video_bio_size = 0
        self._video_q.put(None)
            
    def write_to_proc(self):
        while True:
            try:
                bio = self._video_q.get()
                if bio is None:
                    break
                bio.seek(0)
                shutil.copyfileobj(bio, self._proc.stdin)
                bio.close()
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error(e)
                break
                            
        self._proc.stdin.flush()
        self._proc.stdin.close()
        self._proc.wait()
