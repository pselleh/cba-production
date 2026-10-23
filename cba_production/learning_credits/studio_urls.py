from django.urls import path

from . import studio_views

app_name = "cba_learning_credits_studio"
urlpatterns = [
    path("", studio_views.credit_courses, name="courses"),
    path("course/<path:course_key>/approve/<int:plan_id>/", studio_views.approve_plan, name="approve"),
    path("course/<path:course_key>/export/<int:plan_id>/", studio_views.export_plan, name="export"),
    path("course/<path:course_key>/", studio_views.course_credit_plans, name="course"),
]
