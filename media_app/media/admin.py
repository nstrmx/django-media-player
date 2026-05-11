import re
from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from media.models import Audio, Radio, Tag, Video, Author
from media.admin_filters import FilterPresetBase, M2MFilterBase, FilterPresetViewBase


class TagFilterPreset(FilterPresetBase):
    pass


class AuthorFilterPreset(FilterPresetBase):
    pass


class TagFilterPresetView(FilterPresetViewBase):
    filter_preset_model = TagFilterPreset
    template_name = 'admin/tag_filter_preset_popup.html'
    preset_name = 'tag'


class AuthorFilterPresetView(FilterPresetViewBase):
    filter_preset_model = AuthorFilterPreset
    template_name = 'admin/author_filter_preset_popup.html'
    preset_name = 'author'


class TagFilterPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'media_type', 'created_at')


@admin.register(TagFilterPreset)
class TagFilterPresetAdminRegistered(admin.ModelAdmin):
    list_display = ('name', 'user', 'media_type', 'created_at')


@admin.register(AuthorFilterPreset)
class AuthorFilterPresetAdminRegistered(admin.ModelAdmin):
    list_display = ('name', 'user', 'media_type', 'created_at')


class VisibilityFilter(admin.SimpleListFilter):
    title = _("visibility")
    parameter_name = "visibility"

    def lookups(self, request, model_admin):
        return (
            ("all", _("All")),
            ("visible", _("Visible")),
            ("hidden", _("Hidden")),
        )

    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup if self.value() else lookup == "visible",
                "query_string": cl.get_query_string({self.parameter_name: lookup}, []),
                "display": title,
            }

    def queryset(self, request, queryset):
        if self.value() == "visible":
            return queryset.filter(visible=True)
        if self.value() == "hidden":
            return queryset.filter(visible=False)
        if self.value() == "all":
            return queryset
        return queryset.filter(visible=True)


class TagsFilter(M2MFilterBase):
    title = _("tags")
    filter_prefix = 'tag'
    filter_model = Tag


class AuthorsFilter(M2MFilterBase):
    title = _("authors")
    filter_prefix = 'author'
    filter_model = Author


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("title", "updated")
    list_filter = ("updated",)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("title", "updated")
    list_filter = ("updated",)


def get_play_button(media_id):
    return mark_safe(f"""<button type="button" data-id="{media_id}">▶</button>""")


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
    list_filter = (VisibilityFilter, ("tags", TagsFilter))
    search_fields = ("title",)
    search_params_ptrn = re.compile(r"(@[A-z_]+:[^;]+;)")
    actions = ("hide_selected", "edit_tags")

    @admin.action(description="Hide selected media")
    def hide_selected(self, request, queryset):
        queryset.update(visible=False)

    @admin.action(description="Edit tags on selected media")
    def edit_tags(self, request, queryset):
        if "apply" in request.POST:
            tags_to_add = request.POST.getlist("add_tags")
            tags_to_remove = request.POST.getlist("remove_tags")
            if tags_to_add:
                for tag_id in tags_to_add:
                    tag = Tag.objects.get(pk=tag_id)
                    for item in queryset:
                        item.tags.add(tag)
            if tags_to_remove:
                for tag_id in tags_to_remove:
                    tag = Tag.objects.get(pk=tag_id)
                    for item in queryset:
                        item.tags.remove(tag)
            self.message_user(request, f"Updated tags on {queryset.count()} items.")
            return None
        tags = Tag.objects.all().order_by("title")
        return render(
            request,
            "admin/edit_tags.html",
            {
                "title": "Edit tags on selected media",
                "queryset": queryset,
                "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
                "tags": tags,
            },
        )

    def get_search_results(self, request, queryset, search_term):
        m, n = set(), []
        for it in self.search_params_ptrn.findall(search_term):
            name, query = it.lstrip("@").rstrip(";").split(":", 1)
            if name == "tag":
                tag_list = [p.strip() for p in query.split(",")]
                tags = Tag.objects.filter(title__in=tag_list)
                for tag in tags:
                    n.append(tag)
            elif name == "author":
                author_list = [p.strip() for p in query.split(",")]
                authors = Author.objects.filter(title__in=author_list)
                for author in authors:
                    m.add(author.pk)
        q = Q()
        for it in self.search_params_ptrn.findall(search_term):
            name, query = it.lstrip("@").rstrip(";").split(":", 1)
            if name == "tags":
                title_list = [p.strip() for p in query.split(",")]
                tags = Tag.objects.filter(title__in=title_list)
                for tag in tags:
                    q |= Q(tags__in=[tag])
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        queryset = queryset.filter(q)
        if m:
            queryset = queryset.filter(authors__in=m)
        if n:
            queryset = queryset.filter(tags__in=n)
        return queryset, use_distinct
    
    def get_tags(self, audio):
        return ", ".join(t.title for t in audio.tags.all())

    def get_authors(self, audio):
        return ", ".join(a.title for a in audio.authors.all())
    
    def play(self, audio):
        return get_play_button(audio.id)


@admin.register(Audio)
class AudioAdmin(MediaAdmin):
    change_list_template = "media/admin/audio_change_list.html"
    change_form_template = "media/admin/audio_change_form.html"
    model = Audio
    list_display = ("title", "play", "get_tags", "get_authors", "duration", "file_size", "updated")
    list_filter = (VisibilityFilter, ("tags", TagsFilter), ("authors", AuthorsFilter))
    readonly_fields = ("duration", "file_size", "md5_hex", "updated")


@admin.register(Radio)
class RadioAdmin(MediaAdmin):
    change_list_template = "media/admin/radio_change_list.html"
    change_form_template = "media/admin/radio_change_form.html"
    model = Radio
    list_display = ("title", "play", "get_tags", "quality", "updated")
    list_filter = (VisibilityFilter, ("tags", TagsFilter), "quality")
    readonly_fields = ("updated",)


@admin.register(Video)
class VideoAdmin(MediaAdmin):
    change_list_template = "media/admin/video_change_list.html"
    change_form_template = "media/admin/video_change_form.html"
    model = Video
    list_display = ("title", "play", "get_tags", "duration", "get_file_size", "updated")
    list_filter = (VisibilityFilter, ("tags", TagsFilter))
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
