import re
from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from media.models import Audio, Radio, Tag, Video, Author


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


class TagsFilter(admin.RelatedFieldListFilter):
    title = _("tags")
    parameter_name = "tags"
    template = "admin/tags_filter.html"

    @property
    def include_empty_choice(self):
        return False

    def field_choices(self, field, request, model_admin):
        tag_set = set()
        qs = model_admin.get_queryset(request)
        for item in qs:
            if item.tags.count() > 0:
                for v in item.tags.values_list("id", "title"):
                    tag_set.add(v)
        return sorted(tag_set, key=lambda it: it[1])

    def choices(self, changelist):
        tag_counts = {}
        qs = changelist.queryset
        for item in qs:
            for tag in item.tags.all():
                tag_counts[tag.id] = tag_counts.get(tag.id, 0) + 1

        selected_ids = set(self.request.GET.getlist('tags'))
        for pk_val, display in self.lookup_choices:
            selected = str(pk_val) in selected_ids
            query_string = changelist.get_query_string({self.lookup_kwarg: pk_val})
            yield {
                "pk": pk_val,
                "selected": selected,
                "query_string": query_string,
                "display": display,
                "has_media": pk_val in tag_counts,
            }

    def queryset(self, request, queryset):
        tags_or = request.GET.getlist('tags')
        tags_and = request.GET.getlist('tags_and')
        tags_not = request.GET.getlist('tags_not')

        if tags_or:
            from django.db.models import Q
            q = Q()
            for tag_id in tags_or:
                q |= Q(tags=tag_id)
            queryset = queryset.filter(q)

        if tags_and:
            for tag_id in tags_and:
                queryset = queryset.filter(tags=tag_id)

        if tags_not:
            for tag_id in tags_not:
                queryset = queryset.exclude(tags=tag_id)

        return queryset

    def expected_parameters(self):
        return ['tags', 'tags_and', 'tags_not']


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
    list_filter = (VisibilityFilter, ("tags", TagsFilter),)
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

    def get_authors(self, audio):
        return ", ".join(a.title for a in audio.authors.all())
    
    def play(self, audio):
        return get_play_button(audio.id)


@admin.register(Audio)
class AudioAdmin(MediaAdmin):
    change_list_template = "media/admin/audio_change_list.html"
    change_form_template = "media/admin/audio_change_form.html"
    model = Audio
    list_display = ("title", "play", "duration", "get_tags", "get_authors", "updated", "get_file_size")
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
    list_filter = (VisibilityFilter, ("tags", TagsFilter), "quality")
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
