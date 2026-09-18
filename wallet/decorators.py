from functools import wraps
from .models import IdempotencyKey
from django.http import JsonResponse
import json


def idempotent(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        key = request.headers.get('Idempotency-Key')
        if not key:
            return view_func(request, *args, **kwargs)

        existing = IdempotencyKey.objects.filter(key=key).first()
        if existing:
            return JsonResponse(
                existing.response_data,
                status=existing.status_code,
                safe=False,
            )

        response = view_func(request, *args, **kwargs)
        if 200 <= response.status_code < 300:
            try:
                data = json.loads(response.content)
            except (json.JSONDecodeError, AttributeError):
                data = {"detail": "non-json response"}
            IdempotencyKey.objects.create(
                key=key,
                response_data=data,
                status_code=response.status_code,
            )
        return response
    return wrapper
