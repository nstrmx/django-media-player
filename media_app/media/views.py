from datetime import timedelta
from django.views import View
from django.http.request import HttpRequest
from django.http.response import StreamingHttpResponse, JsonResponse, HttpResponse
from media.models import Audio, Radio, Video


Media = Audio | Radio | Video


class ViewBaseFileStream(View):
    content_type = "application/octet-stream"

    def get(self, request: HttpRequest) -> StreamingHttpResponse:
        object = self.get_object()
        if object is None:
            return StreamingHttpResponse(iter([b""]))
        response = StreamingHttpResponse(
            object.get_fd_iterator(), 
            content_type=self.content_type,
        )
        response = self.update_response_headers(object, response)
        return response
    
    def get_object(self) -> Media:
        raise NotImplementedError()
    
    def update_response_headers(self, object: Media, response: StreamingHttpResponse) -> StreamingHttpResponse:
        return response
    

class ViewMediaFileStream(ViewBaseFileStream):   
    def get_object(self) -> Media | None:
        media_id = self.request.GET.get("id")
        media_type = self.request.GET.get("type")
        match media_type:
            case "audio":
                media_class = Audio
            case "radio":
                media_class = Radio
            case "video":
                media_class = Video
            case _:
                raise NotImplementedError()
        return media_class.objects.filter(id=media_id).first()
    
    def update_response_headers(self, object: Media, response: StreamingHttpResponse) -> StreamingHttpResponse:
        if isinstance(object, (Audio, Video)):
            fsize = object.get_processed_path().stat().st_size
            if object.file_size == 0:
                object.file_size = fsize
                object.save()
            response["Accept-Ranges"] = "bytes"
            response["Content-Length"] = fsize
            response["Content-Range"] = f"bytes 0-{fsize-1}/{fsize}"
            return response
        elif isinstance(object, Radio):
            return response
        else:
            raise NotImplementedError()


class ViewMediaUpdateDuration(View):
    def post(self, request: HttpRequest) -> JsonResponse:
        media_id = request.POST.get("id")
        media_type = request.POST.get("type")
        dur = request.POST.get("duration")
        if dur is None:
            return JsonResponse(dict(), status=400)
        duration = int(float(dur))
        match media_type:
            case "audio":
                media_class = Audio        
            case "video":
                media_class = Video
            case _:
                raise NotImplementedError()
        media = media_class.objects.get(id=media_id)
        media.duration = timedelta(seconds=duration)
        media.save()
        return JsonResponse(dict(), status=200)
    

class ViewMediaUpdatePlayCount(View):
    def post(self, request: HttpRequest) -> JsonResponse:
        media_id = request.POST.get("id")
        media_type = request.POST.get("type")
        if media_id is None:
            return JsonResponse(dict(), status=400)
        match media_type:
            case "audio":
                media_class = Audio
            case "radio":
                media_class = Radio
            case "video":
                media_class = Video
            case _:
                raise NotImplementedError()
        media = media_class.objects.get(id=media_id)
        media.play_count = media.play_count + 1
        media.save()
        return JsonResponse(dict(), status=200)
    

class ViewPlayer(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        from django.template.loader import render_to_string
        content = render_to_string("media/player.html", {})
        return HttpResponse(content)