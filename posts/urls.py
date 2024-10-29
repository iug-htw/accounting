from django.urls import path, include
from . import views

app_name = 'posts'

urlpatterns = [
    path('', views.buchungsaufgabe_view, name="list"),
    path('buchung_uebersicht/', views.buchung_uebersicht_view, name='buchung_uebersicht'),
    path('buchungsaufgabe/', views.buchungsaufgabe_view, name = 'buchungsaufgabe'),
    path('neue-aufgabe/', views.neue_aufgabe, name='neue_aufgabe'),
    path('aufgaben/', views.aufgaben_liste, name='aufgaben_liste'),
    path('neue-kategorie/', views.neue_kategorie, name='neue_kategorie'),
    path('kategorie-loeschen/<int:kategorie_id>/', views.kategorie_loeschen, name='kategorie_loeschen'),
    path('kategorien/', views.kategorien_liste, name='kategorien_liste'),  # Zeigt alle Kategorien an
    path('kategorie/<int:kategorie_id>/', views.kategorie_aufgaben, name='kategorie_aufgaben'),  # Zeigt Aufgaben nach Kategorie
    path('aufgabe/<int:aufgabe_id>/', views.aufgabe_detail, name='aufgabe_detail'), 
    path('alle_aufgaben/', views.alle_aufgaben, name='alle_aufgaben'),
    path('update_aufgabe_status/<int:aufgabe_id>/', views.update_aufgabe_status, name='update_aufgabe_status'),
    path('nicht_abgeschlossene_aufgaben/', views.nicht_abgeschlossene_aufgaben_view, name='nicht_abgeschlossene_aufgaben'),
    path('update_aufgabe_status_multiple/', views.update_aufgabe_status_multiple, name='update_aufgabe_status_multiple'),
]