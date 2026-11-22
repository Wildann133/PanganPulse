from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/ringkasan", views.api_ringkasan, name="api_ringkasan"),
]
