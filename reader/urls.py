from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'reader'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('posts/', views.posts_list, name='posts_list'),
    path('videos/', views.videos_list, name='videos_list'),
    path('<int:year>/<str:month>/<str:day>/<slug:slug>/', views.post_detail, name='post_detail'),
    path('update-progress/', views.update_progress, name='update_progress'),
    path('sync-feed/', views.sync_feed, name='sync_feed'),
    path('service-worker.js', TemplateView.as_view(template_name='service-worker.js', content_type='application/javascript'), name='service_worker'),
]
