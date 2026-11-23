"""Mount the real shared routes and the processor's Django plugin routes."""
from django.urls import include, path
urlpatterns = [path('redsys/', include('eox_redsys.urls')), path('', include('zeitlabs_payments.urls'))]
