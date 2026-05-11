import json
from django.contrib import admin
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View


class FilterPresetBase(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('audio', 'Audio'),
        ('radio', 'Radio'),
        ('video', 'Video'),
    ]
    name = models.CharField(max_length=100)
    state = models.JSONField(default=list)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'user', 'media_type')
        abstract = True

    def __str__(self):
        return self.name


class M2MFilterBase(admin.RelatedFieldListFilter):
    filter_prefix = None
    filter_model = None
    template = "admin/m2m_filter.html"

    @property
    def label(self):
        return self.filter_prefix

    def has_output(self):
        if self.filter_prefix == 'author' and not hasattr(self.model, 'authors'):
            return False
        return True

    def __init__(self, field, request, params, model, model_admin, **kwargs):
        super().__init__(field, request, params, model, model_admin, **kwargs)
        self.model = model

    @property
    def include_empty_choice(self):
        return False

    def field_choices(self, field, request, model_admin):
        obj_set = set()
        qs = model_admin.get_queryset(request)
        for item in qs:
            rel_items = self._get_related(item)
            if rel_items and rel_items.count() > 0:
                for v in rel_items.values_list("id", "title"):
                    obj_set.add(v)
        return sorted(obj_set, key=lambda it: it[1])

    def _get_related(self, item):
        return getattr(item, self.filter_prefix+'s', None)

    def _get_choices(self, changelist, field_name, param_or, param_and, param_not):
        counts = {}
        qs = changelist.queryset
        for item in qs:
            rel_items = self._get_related(item)
            if rel_items:
                for it in rel_items.all():
                    counts[it.pk] = counts.get(it.pk, 0) + 1
        self.filter_media_type = self.model._meta.model_name
        choices_list = []
        for pk_val, display in self.lookup_choices:
            query_string = changelist.get_query_string({self.lookup_kwarg: pk_val})
            choices_list.append({
                "pk": pk_val,
                "query_string": query_string,
                "display": display,
                "has_media": pk_val in counts,
            })
        return choices_list

    def choices(self, changelist):
        choices_list = self._get_choices(
            changelist,
            self.filter_prefix + 's',
            self.filter_prefix + 's',
            self.filter_prefix + 's_and',
            self.filter_prefix + 's_not'
        )
        self.choices_list = choices_list
        return choices_list

    def queryset(self, request, queryset):
        param_or = self.filter_prefix + 's'
        param_and = self.filter_prefix + 's_and'
        param_not = self.filter_prefix + 's_not'
        items_or = request.GET.getlist(param_or)
        items_and = request.GET.getlist(param_and)
        items_not = request.GET.getlist(param_not)
        filter_field = self.filter_prefix + 's'
        if items_or:
            q = Q()
            for item_id in items_or:
                q |= Q(**{filter_field: item_id})
            queryset = queryset.filter(q)
        if items_and:
            for item_id in items_and:
                queryset = queryset.filter(**{filter_field: item_id})
        if items_not:
            for item_id in items_not:
                queryset = queryset.exclude(**{filter_field: item_id})
        return queryset

    def expected_parameters(self):
        prefix = self.filter_prefix + 's'
        return [prefix, prefix + '_and', prefix + '_not']


class FilterPresetViewBase(View):
    filter_preset_model = None
    template_name = None
    preset_name = None

    def get(self, request, preset_id=None):
        media_type = request.GET.get('media_type', 'audio')
        model = self.filter_preset_model
        if request.GET.get('_popup'):
            presets = list(model.objects.filter(user=request.user, media_type=media_type).values('id', 'name', 'state', 'created_at'))
            for p in presets:
                p['state_json'] = json.dumps(p.pop('state'))
            return render(request, self.template_name, {'presets': presets, 'media_type': media_type, 'preset_name': self.preset_name})
        presets = list(model.objects.filter(user=request.user, media_type=media_type).values('id', 'name', 'state', 'created_at'))
        return JsonResponse(presets, safe=False)

    def post(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name')
            state = data.get('state', [])
            media_type = data.get('media_type', 'audio')
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            model = self.filter_preset_model
            preset = model.objects.create(name=name, state=state, user=request.user, media_type=media_type)
            return JsonResponse({'id': preset.id, 'name': preset.name, 'state': preset.state, 'created_at': preset.created_at.isoformat()}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

    def delete(self, request, preset_id):
        try:
            model = self.filter_preset_model
            preset = model.objects.get(id=preset_id, user=request.user)
            preset.delete()
            return JsonResponse({'status': 'deleted'})
        except model.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
