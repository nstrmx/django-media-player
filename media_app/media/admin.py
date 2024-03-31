import re
from django.contrib import admin
from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from media.models import Audio, Radio, Tag, Video


class TagsFilter(admin.RelatedFieldListFilter):
    title = _("tags")
    parameter_name = "tags"

    @property
    def include_empty_choice(self):
        return True

    def field_choices(self, field, request, model_admin):
        tag_set = set()
        qs = self.queryset(request, model_admin.get_queryset(request))
        if qs is None:
            return ()
        for item in qs:
            if item.tags.count() > 0:
                v = item.tags.values_list("id", "title")
                tag_set.update(v)
        return sorted(tag_set, key=lambda it: it[1])


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("title", "updated")
    list_filter = ("updated",)
    


def get_play_button(media_id):
    return mark_safe(f"""<button type="button" data-id="{media_id}">play</button>""")


class PlayWidget(forms.Widget):
    def render(self, name, value, **kwargs):
        return get_play_button(value)


class PlayField(forms.Field):
    widget = PlayWidget


class MediaModelForm(forms.ModelForm):
    play = PlayField(required=False)

    def __init__(self, *args, **kwargs):
        media = kwargs.get("instance")
        super().__init__(*args, **kwargs)
        if media is None:
            return
        self.initial["play"] = media.id


class MediaAdmin(admin.ModelAdmin):
    change_list_template = "media/admin/media_change_list.html"
    change_form_template = "media/admin/media_change_form.html"
    form = MediaModelForm
    list_filter = (("tags", TagsFilter),)
    search_fields = ("title",)
    search_params_ptrn = re.compile(r"(@[A-z_]+:[^;]+;)")

    def get_search_results(self, request, queryset, search_term):
        m = self.search_params_ptrn.findall(search_term)
        q = Q()
        if len(m) > 0:
            for it in m:
                search_term = search_term.replace(it, "")
                name, query = it.lstrip("@").rstrip(";").split(":", 1)
                if name == "tags":
                    title_list = [p.strip() for p in query.split(",")]
                    tags = Tag.objects.filter(title__in=title_list)
                    for tag in tags:
                        q |= Q(tags__in=[tag])
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        queryset = queryset.filter(q)
        return queryset, use_distinct
    
    def get_tags(self, audio):
        return ", ".join(t.title for t in audio.tags.all())
    
    def play(self, audio):
        return get_play_button(audio.id)


@admin.register(Audio)
class AudioAdmin(MediaAdmin):
    change_list_template = "media/admin/audio_change_list.html"
    change_form_template = "media/admin/audio_change_form.html"
    model = Audio
    list_display = ("title", "play", "duration", "get_tags", "updated", "get_file_size")
    readonly_fields = ("duration", "file_size", "md5_hex", "updated")

    def get_file_size(self, audio):
        value = audio.file_size
        c = ""
        if value > 1024:
            value = value / 1024
            c = "K"
        if value > 1024:
            value = value / 1024
            c = "M"
        if value > 1024:
            value = value / 1024
            c = "G"
        return f"{round(value, 2)} {c}b"
    

@admin.register(Radio)
class RadioAdmin(MediaAdmin):
    change_list_template = "media/admin/radio_change_list.html"
    change_form_template = "media/admin/radio_change_form.html"
    model = Radio
    list_display = ("title", "play", "get_tags", "quality", "updated")
    list_filter = (("tags", TagsFilter), "quality")
    readonly_fields = ("updated",)
    

@admin.register(Video)
class VideoAdmin(MediaAdmin):
    change_list_template = "media/admin/video_change_list.html"
    change_form_template = "media/admin/video_change_form.html"
    model = Video
    list_display = ("title", "play", "duration", "get_tags", "updated", "get_file_size")
    readonly_fields = ("duration", "file_size", "md5_hex", "updated")

    def get_file_size(self, audio):
        value = audio.file_size
        c = ""
        if value > 1024:
            value = value / 1024
            c = "K"
        if value > 1024:
            value = value / 1024
            c = "M"
        if value > 1024:
            value = value / 1024
            c = "G"
        return f"{round(value, 2)} {c}b"