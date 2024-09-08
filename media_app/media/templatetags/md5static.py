import hashlib
import threading
from os import path
from django import template
from django.conf import settings

register = template.Library()


class StaticUrlCache(object):
    _md5_sum = {}
    _lock = threading.Lock()

    @classmethod
    def get_url(cls, file):
        try:
            return cls._md5_sum[file]
        except KeyError:
            with cls._lock:
                try:
                    md5 = cls.calc_md5(path.join(settings.STATIC_ROOT, file))[:8]
                    value = '%s%s?v=%s' % (settings.STATIC_URL, file, md5)
                except IsADirectoryError:
                    value = settings.STATIC_URL + file
                cls._md5_sum[file] = value
                return value

    @classmethod
    def calc_md5(cls, file_path):
        with open(file_path, 'rb') as fh:
            m = hashlib.md5()
            while True:
                data = fh.read(4096)
                if not data:
                    break
                m.update(data)
            return m.hexdigest()


@register.simple_tag
def md5static(model_object):
    return StaticUrlCache.get_url(model_object)