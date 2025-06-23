from datetime import timedelta
from hashlib import md5
import mimetypes
import json
from multiprocessing import Process, RLock, cpu_count, Queue
import os
from pathlib import Path
import signal
import subprocess
import sys
from django.core.management.base import BaseCommand, CommandParser
from media.models import Audio, Video


def eprint(*args, **kwargs):
    print("error:", *args, **kwargs, file=sys.stderr)
    

class Command(BaseCommand):
    help = "Add media from your media directory"
    lock = RLock()
    chunk_size = 1024 * 1024
    cpu_count = cpu_count()
    has_ffprobe = False
    DONE = "DONE"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_ffprobe = has_ffprobe()

    def add_arguments(self, parser: CommandParser) -> None:
        self.add_base_argument(  # type: ignore
            parser,
            "--skip-existing-paths",
            action="store_true",
            dest="skip_existing_paths",
            help="skip existing paths",
        )
        parser.add_argument('paths', nargs='+', type=Path, help='List of paths to process')

    def handle(self, *args, **options):
        self.skip_existing_paths = options["skip_existing_paths"]
        workers: list[Process] = []
        task_queue = Queue()
        print("cpu count:", self.cpu_count)
        for i in range(self.cpu_count):
            worker = Process(target=self.worker, args=(task_queue,))
            worker.daemon = True
            worker.start()
            workers.append(worker)
        try:
            for media_path in options["paths"]:
                if not media_path:
                    continue
                if not media_path.exists():
                    eprint(media_path, "does not exist")
                    continue
                if media_path.is_dir():
                    for path, _, files in os.walk(media_path):
                        for fname in files:
                            file_path = Path(path) / fname
                            task_queue.put(file_path)
                else:
                    task_queue.put(media_path)
            for worker in workers:
                task_queue.put(self.DONE)
            for worker in workers:
                if worker.is_alive():
                    worker.join()
            task_queue.close()
            task_queue.join_thread()
        except KeyboardInterrupt:
            eprint("process recieved SIGINT")
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join()
            task_queue.close()
            task_queue.cancel_join_thread()
        

    def worker(self, task_queue):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            while True:
                task = task_queue.get()
                if task == self.DONE:
                    print("worker recieved", self.DONE)
                    return
                self.process_file(task)
        except KeyboardInterrupt:
            eprint("worker recieved SIGINT")

    def process_file(self, file_path):
        if self.skip_existing_paths:
            if (Audio.objects.filter(path=str(file_path)).exists()
                    or Video.objects.filter(path=str(file_path)).exists()):
                eprint("skipping existing", file_path)
                return
        fields = dict(
            title=file_path.stem,
            path=str(file_path),
            file_size=file_path.stat().st_size,
        )
        media_type = resolve_media_type(file_path)
        media_class = None
        match media_type:
            case "audio":
                media_class = Audio
            case "video":
                media_class = Video
            case _:
                eprint(f"unsupported media type", file_path)
                return
        if self.has_ffprobe:
            try:
                file_info = ffprobe(file_path)
                if duration := get_media_duration(file_info):
                    fields["duration"] = duration
            except PopenError as e:
                eprint(f"ffprobe: {e}")
                pass
        md5_hex = get_md5_hex(file_path)
        fields["md5_hex"] = md5_hex
        with self.lock:
            try:
                media_class.objects.update_or_create(defaults=fields, md5_hex=md5_hex)
                print(file_path)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                eprint(file_path, e)


def resolve_media_type(file_path):
    mtype, _ = mimetypes.guess_type(file_path)
    if mtype and mtype[:5] in ("audio", "video"):
        media_type = mtype[:5]
        return media_type


class PopenError(Exception):
    pass

def popen(*args):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise PopenError(err)
    return out


def get_md5_hex(path):
    md5_buf = md5(b"")
    with path.open("rb") as file:
        chunk = file.read(Command.chunk_size)
        while chunk:
            md5_buf.update(chunk)
            chunk = file.read(Command.chunk_size)
    return md5_buf.hexdigest()


def has_ffprobe():
    try:
        out = popen('ffprobe', '-version')
        return True
    except PopenError:
        return False

def ffprobe(path):
    out = popen('ffprobe', '-show_format', '-show_streams', '-of', 'json', path)
    return json.loads(out.decode('utf-8'))


def get_media_duration(data):
    if "format" in data and "duration" in data["format"]:
        duration = float(data["format"]["duration"])
        delta = timedelta(seconds=round(duration, 0))
        return delta


def get_media_type(data):
    has_audio = False
    if 'format' in data and data['format'].get("format_name", "").startswith("image"):
        return
    if 'streams' in data:
        for stream in data['streams']:
            if stream.get('codec_type') == 'video':
                codec_name = stream.get('codec_name')
                if isinstance(codec_name, str):
                    if 'jpeg' in codec_name or 'jpg' in codec_name:
                        return
                if codec_name in ('ansi', 'png', 'pictor', 'gif', 'bmp', 'svg', 'tiff', 'webp', ''):
                    return
                return 'video'
            elif stream.get('codec_type') == 'audio':
                has_audio = True
    if has_audio:
        return 'audio'
