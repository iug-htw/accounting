from django.urls import path, include
from . import views

app_name = 'posts'

urlpatterns = [
    path('', views.buchungsaufgabe_view, name="list"),
    path('buchungsaufgabe/', views.buchungsaufgabe_view, name = 'buchungsaufgabe'),
    path('neue-aufgabe/', views.neue_aufgabe, name='neue_aufgabe'),
    path('aufgaben/', views.aufgaben_liste, name='aufgaben_liste'),
    path('neue-kategorie/', views.neue_kategorie, name='neue_kategorie'),
    path('kategorie-loeschen/<int:kategorie_id>/', views.kategorie_loeschen, name='kategorie_loeschen'),
    path('kategorien/', views.kategorien_liste, name='kategorien_liste'),  # Zeigt alle Kategorien an
    path('kategorie/<int:kategorie_id>/', views.kategorie_aufgaben, name='kategorie_aufgaben'),  # Zeigt Aufgaben nach Kategorie
    path('aufgabe/<int:aufgabe_id>/', views.aufgabe_detail, name='aufgabe_detail'),  # New path for task detail page    
]