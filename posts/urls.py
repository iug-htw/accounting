from django.urls import path, include
from . import views

app_name = 'posts'

urlpatterns = [
    path('', views.posts_list, name="list"),
    path('new-post/', views.post_new, name="new-post"),
    path('<slug:slug>', views.post_page, name="page"),
    path('buchungsaufgabe/', views.buchungsaufgabe_view, name = 'buchungsaufgabe'),
    path('neue-aufgabe/', views.neue_aufgabe, name='neue_aufgabe'),
    path('aufgaben/', views.aufgaben_liste, name='aufgaben_liste'),    
]