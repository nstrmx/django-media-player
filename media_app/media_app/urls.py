from django.contrib import admin
from django.urls import path, include
from media.admin import TagFilterPresetView, AuthorFilterPresetView

urlpatterns = [
    path("admin/api/tag-filter-presets/", TagFilterPresetView.as_view(), name="tag-filter-presets"),
    path("admin/api/tag-filter-presets/<int:preset_id>/", TagFilterPresetView.as_view(), name="tag-filter-preset-detail"),
    path("admin/api/author-filter-presets/", AuthorFilterPresetView.as_view(), name="author-filter-presets"),
    path("admin/api/author-filter-presets/<int:preset_id>/", AuthorFilterPresetView.as_view(), name="author-filter-preset-detail"),
    path("admin/", admin.site.urls),
    path("media/", include("media.urls"))
]
