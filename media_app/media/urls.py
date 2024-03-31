from django.urls import path
from media.views import *

urlpatterns = [
    path(r"media-file-stream/", ViewMediaFileStream.as_view(), name="media-file-stream"),
    path(r"media-update-duration/", ViewMediaUpdateDuration.as_view(), name="media-update-duration"),
]