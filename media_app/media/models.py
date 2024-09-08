from datetime import timedelta
from hashlib import md5
from pathlib import Path
from urllib.parse import urlparse, unquote
from urllib.request import urlopen
from django.db import models


class Tag(models.Model):
    class Meta:
        ordering = ("title",)

    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=200, blank=False, null=False)
    description = models.TextField(blank=True, null=False, default="")

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"<{self.__class__.__name__} pk={self.pk} title=\"{self.title[:50]}>\""


class Media(models.Model):
    chunk_size = 1024 * 10

    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=200, blank=False, null=False)
    path = models.CharField(max_length=200, blank=False, null=False, unique=True)
    description = models.TextField(blank=True, null=False, default="")
    tags = models.ManyToManyField(Tag)
    play_count = models.IntegerField(blank=False, null=False, default=0)

    class Meta:
        abstract = True

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"<{self.__class__.__name__} pk={self.pk} title=\"{self.title[:50]}>\""
    
    def get_processed_path(self):
        raise NotImplementedError()
    
    def get_fd_iterator(self):
        raise NotImplementedError()


class Audio(Media):
    chunk_size = 1024 * 1024

    file_size = models.IntegerField(blank=False, null=False, default=0)
    md5_hex = models.CharField(max_length=200, blank=False, null=False, unique=True)
    duration = models.DurationField(blank=False, null=False, default=timedelta(seconds=0))
    
    def get_processed_path(self):
        if self.path.startswith("file://"):
            file_path = Path(unquote(urlparse(self.path).path))
        elif self.path.startswith("/home/"):
            file_path = Path(self.path)
        else:
            raise NotImplementedError()
        return file_path
    
    def get_fd_iterator(self):
        chunk_size = self.__class__.chunk_size
        with self.get_processed_path().open("rb") as file:
            if self.md5_hex == "":
                md5_buf = md5(b"")
                chunk = file.read(chunk_size)
                while chunk:
                    md5_buf.update(chunk)
                    yield chunk
                    chunk = file.read(chunk_size)
                self.md5_hex = md5_buf.hexdigest()
                self.save()
            else:
                chunk = file.read(chunk_size)
                while chunk:
                    yield chunk
                    chunk = file.read(chunk_size)
    

class Radio(Media):
    chunk_size = 1024

    quality = models.CharField(max_length=1, choices=(("l", "low"), ("m", "medium"), ("h", "high")))

    def get_processed_path(self):
        return urlparse(self.path)
    
    def get_fd_iterator(self):
        chunk_size = self.__class__.chunk_size
        with urlopen(self.get_processed_path().geturl()) as file:
            chunk = file.read(chunk_size)
            while chunk:
                yield chunk
                chunk = file.read(chunk_size)


class Video(Media):
    chunk_size = 1024 * 1024

    file_size = models.IntegerField(blank=False, null=False, default=0)
    md5_hex = models.CharField(max_length=200, blank=False, null=False, unique=True)
    duration = models.DurationField(blank=False, null=False, default=timedelta(seconds=0))
    
    def get_processed_path(self):
        if self.path.startswith("file://"):
            file_path = Path(unquote(urlparse(self.path).path))
        elif self.path.startswith("/home/"):
            file_path = Path(self.path)
        else:
            raise NotImplementedError()
        return file_path
    
    def get_fd_iterator(self):
        chunk_size = self.__class__.chunk_size
        with self.get_processed_path().open("rb") as file:
            if self.md5_hex == "":
                md5_buf = md5(b"")
                chunk = file.read(chunk_size)
                while chunk:
                    md5_buf.update(chunk)
                    yield chunk
                    chunk = file.read(chunk_size)
                self.md5_hex = md5_buf.hexdigest()
                self.save()
            else:
                chunk = file.read(chunk_size)
                while chunk:
                    yield chunk
                    chunk = file.read(chunk_size)
