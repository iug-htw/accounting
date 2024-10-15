from django.urls import path, include
from . import views

app_name = 'posts'

urlpatterns = [
    path('', views.buchungsaufgabe_view, name="list"),
    path('buchungsaufgabe/', views.buchungsaufgabe_view, name = 'buchungsaufgabe'),
    path('neue-aufgabe/', views.neue_aufgabe, name='neue_aufgabe'),
    path('aufgaben/', views.aufgaben_liste, name='aufgaben_liste'),
    path('aufgabe/<int:aufgabe_id>/', views.aufgabe_detail, name='aufgabe_detail'),  # New path for task detail page    
]