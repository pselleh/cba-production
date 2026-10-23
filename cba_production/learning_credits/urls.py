from django.urls import path

from .views import learner_credit_page, learner_credit_record


app_name = "cba_learning_credits"

urlpatterns = [
    path("", learner_credit_page, name="record"),
    path("api/", learner_credit_record, name="record-api"),
]
