from django.contrib import admin
from django.urls import path, include
from media.admin import TagFilterPresetView

urlpatterns = [
    path("admin/api/tag-filter-presets/", TagFilterPresetView.as_view(), name="tag-filter-presets"),
    path("admin/api/tag-filter-presets/<int:preset_id>/", TagFilterPresetView.as_view(), name="tag-filter-preset-detail"),
    path("admin/", admin.site.urls),
    path("media/", include("media.urls"))
]
