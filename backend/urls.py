import os
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.shortcuts import redirect
from django.http import Http404
from django.views.static import serve


def media_serve(request, path):
    """
    Serves media files:
    1. From local MEDIA_ROOT if the physical file exists on disk.
    2. Fallback to S3 cloud storage if configured (redirects to presigned URL).
    """
    full_local_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(full_local_path):
        return serve(request, path, document_root=settings.MEDIA_ROOT)

    if getattr(settings, 'AWS_ACCESS_KEY_ID', None) and getattr(settings, 'AWS_S3_ENDPOINT_URL', None):
        try:
            from storages.backends.s3boto3 import S3Boto3Storage
            storage = S3Boto3Storage(
                access_key=settings.AWS_ACCESS_KEY_ID,
                secret_key=settings.AWS_SECRET_ACCESS_KEY,
                bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                region_name=settings.AWS_S3_REGION_NAME,
            )
            s3_path = path.replace('\\', '/')
            if storage.exists(s3_path):
                return redirect(storage.url(s3_path))
        except Exception as exc:
            print(f"S3 media serve error: {exc}")

    raise Http404(f"'{path}' does not exist")


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/journals/', include('journals.urls')),
    path('api/notifications/', include('user_notifications.urls')),
    re_path(r'^media/(?P<path>.*)$', media_serve, name='media_serve'),
]