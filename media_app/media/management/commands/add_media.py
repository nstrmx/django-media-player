from datetime import timedelta
from hashlib import md5
import json
from multiprocessing import Process, RLock, cpu_count, Queue
import os
from pathlib import Path
import subprocess
import sys
from django.core.management.base import BaseCommand, CommandParser
from media.models import Audio, Video


class Command(BaseCommand):
    help = "Add media from your media directory"
    lock = RLock()
    chunk_size = 1024 * 1024
    cpu_count = cpu_count()
    DONE = "DONE"

    def add_arguments(self, parser: CommandParser) -> None:
        self.add_base_argument(  # type: ignore
            parser,
            "--audio-dir",
            type=Path,
            dest="audio_dir",
            help="path to audio directory",
        )
        self.add_base_argument(  # type: ignore
            parser,
            "--video-dir",
            type=Path,
            dest="video_dir",
            help="path to video directory",
        )
        self.add_base_argument(  # type: ignore
            parser,
            "--skip-existing-paths",
            action="store_true",
            dest="skip_existing_paths",
            help="skip existing paths",
        )

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
        for key, media_class in (("audio_dir", Audio), ("video_dir", Video)):
            media_dir = options[key]
            if not media_dir:
                continue
            if not media_dir.exists():
                print("error:", media_dir, "does not exist")
                continue
            for path, _, files in os.walk(media_dir):
                for fname in files:
                    file_path = Path(path) / fname
                    task_queue.put((file_path, media_class))
        for worker in workers:
            task_queue.put(self.DONE)
        for worker in workers:
            worker.join()
        task_queue.close()
        task_queue.join_thread()

    def worker(self, task_queue):
        while True:
            task = task_queue.get()
            if task == self.DONE:
                print("recieved:", self.DONE)
                return
            file_path, media_class = task
            self.process_file(file_path, media_class)

    def process_file(self, file_path, media_class):
        if self.skip_existing_paths:
            if media_class.objects.filter(path=str(file_path)).exists():
                print("skipping existing:", file_path)
                return
        md5_hex = get_md5_hex(file_path)
        fields = dict(
            title=file_path.stem,
            path=str(file_path),
            md5_hex=md5_hex,
            file_size=file_path.stat().st_size,
        )
        if duration := get_media_duration(file_path):
            fields["duration"] = duration
        with self.lock:
            try:
                media_class.objects.update_or_create(defaults=fields, md5_hex=md5_hex)
                print(file_path)
            except Exception as e:
                print("error:", file_path, e, file=sys.stderr)


def popen(*args):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise Exception(err)
    return out


def default_md5(path):
    md5_buf = md5(b"")
    with file_path.open("rb") as file:
        chunk = file.read(self.chunk_size)
        while chunk:
            md5_buf.update(chunk)
            chunk = file.read(self.chunk_size)
    return md5_buf.hexdigest()

md5_method = None


def get_md5_hex(path):
    global md5_method
    res = None
    try:
        match md5_method:
            case "default":
                res = default_md5(path)
            case "md5sum":
                out = popen("md5sum", path)
                res = out.strip().lower()[:32]
            case "md5":
                out = popen("md5", path)
                res = out.strip().lower()[-32:]
            case "openssl":
                out = popen("openssl", "md5", path)
                res = out.strip().lower()[-32:]
            case _:
                match sys.platform:
                    case "linux":
                        try:
                            out = popen("md5sum", path)
                            res = out.strip().lower()[:32]
                            md5_method = "md5sum"
                        except Exception:
                            out = popen("openssl", "md5", path)
                            res = out.strip().lower()[-32:]
                            md5_method = "openssl"
                    case "darwin":
                        try:
                            out = popen("md5", path)
                            res = out.strip().lower()[-32:]
                            md5_method = "md5"
                        except Exception:
                            out = popen("openssl", "md5", path)
                            res = out.strip().lower()[-32:]
                            md5_method = "openssl"
                    case _:
                        raise Exception
    except Exception:
        res = default_md5(path)
        md5_method = "default"
    if isinstance(res, bytes):
        res = res.decode("utf-8")
    return res


def ffprobe(path):
    out = popen('ffprobe', '-show_format', '-show_streams', '-of', 'json', path)
    return json.loads(out.decode('utf-8'))


def get_media_duration(path):
    try:
        p = ffprobe(path)
        duration = float(p["format"]["duration"])
        delta = timedelta(seconds=round(duration, 0))
        return delta
    except Exception as e:
        print(f"error processing media duration: {path=} {e=}", file=sys.stderr)
        return None

