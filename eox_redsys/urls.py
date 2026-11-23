"""Server-to-server notification endpoint owned by this processor."""
from django.urls import path
from eox_redsys.views import RedsysNotificationView
app_name = 'eox_redsys'
urlpatterns = [path('notification/', RedsysNotificationView.as_view(), name='notification')]
