from django.urls import path
from . import views

app_name = "price_analysis"

urlpatterns = [
    path("price-analysis/", views.index, name="index"),
    path("api/tren/", views.api_price_trend, name="api_tren"),
    path("api/tren/options/", views.api_filter_options, name="api_tren_options"),
    path("api/detail/", views.api_price_detail, name="api_detail"),
]