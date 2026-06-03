from django.urls import path
from . import views

app_name = "summarizer"

urlpatterns = [
    path("", views.home, name="home"),
    path("summarize/", views.summarize_view, name="summarize"),
    path("summary/<int:pk>/", views.summary_detail, name="summary_detail"),
    path("history/", views.history, name="history"),
    path("charts/", views.charts_view, name="charts"),
    path("comparison/", views.comparison_view, name="comparison"),
    path("export/<int:pk>/", views.export_summary, name="export_summary"),
    path("add-to-dataset/<int:pk>/", views.add_to_dataset, name="add_to_dataset"),
    path("download-template/", views.download_template, name="download_template"),
    path("task-status/<str:task_id>/", views.task_status, name="task_status"),
]
