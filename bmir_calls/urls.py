from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import include, path

from .views.twilio import incoming_dialed_api, outgoing_sip_api


def index(request):
    if request.user.is_staff:
        return redirect("admin:index")
    return HttpResponse(
        "There are forty people in the world and five of them are hamburgers.", content_type="text/plain"
    )


urlpatterns = [
    path("", index, name="index"),
    path("twilio/incoming/", incoming_dialed_api.urls),
    path("twilio/outgoing/", outgoing_sip_api.urls),
    path("cmsadmin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns.extend(static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT))
    urlpatterns.append(path("__debug__/", include("debug_toolbar.urls")))
