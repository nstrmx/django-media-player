from django.urls import path
from media.views import *

app_name = "media"

urlpatterns = [
    path(r"media-file-stream/", ViewMediaFileStream.as_view(), name="file-stream"),
    path(r"media-update-duration/", ViewMediaUpdateDuration.as_view(), name="update-duration"),
    path(r"media-update-play-count/", ViewMediaUpdatePlayCount.as_view(), name="update-play-count"),
    path(r"player", ViewPlayer.as_view(), name="player"),
]