"""URLs raíz de LabLocal."""
from django.conf import settings
from django.urls import include, path
from django.views.generic import RedirectView
from django.views.static import serve

from labs.views import LoginView, LogoutView

handler404 = 'labs.views.custom_404'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard'), name='root'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    path('', include('labs.urls')),
]
