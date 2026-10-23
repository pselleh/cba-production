from django.urls import include, path
from cba_production.learning_credits import studio_urls

urlpatterns = [path("credits/", include(studio_urls, namespace="cba_learning_credits_studio"))]
