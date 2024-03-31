import os
from hashlib import md5
from pathlib import Path
from multiprocessing import Process, RLock, cpu_count, Queue
from django.core.management.base import BaseCommand, CommandParser
from media.models import Audio, Video


class Command(BaseCommand):
    help = "Add media from your media directory"
    lock = RLock()
    chunk_size = 1024 * 1024
    cpu_count = cpu_count()
    DONE = "DONE"

    def add_arguments(self, parser: CommandParser) -> None:
        self.add_base_argument(                                                 # type: ignore
            parser,
            "--audio-dir",
            type=Path,
            dest="audio_dir",
            help="path to audio directory"
        )
        self.add_base_argument(                                                 # type: ignore
            parser,
            "--video-dir",
            type=Path,
            dest="video_dir",
            help="path to video directory"
        )
        self.add_base_argument(                                                 # type: ignore
            parser,
            "--skip-existing-paths",
            action="store_true",
            dest="skip_existing_paths",
            help="skip existing paths"
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
        md5_buf = md5(b"")
        with file_path.open("rb") as file:
            chunk = file.read(self.chunk_size)
            while chunk:
                md5_buf.update(chunk)
                chunk = file.read(self.chunk_size)
        md5_hex = md5_buf.hexdigest()
        media = media_class(
            title=file_path.stem,
            path=str(file_path),
            md5_hex=md5_hex,
            file_size=file_path.stat().st_size,
        )
        with self.lock:
            try:
                media.save()
                print(file_path)
            except Exception as e:
                print("error:", file_path, e)        
