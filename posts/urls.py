from django.urls import path, include
from . import views

app_name = 'posts'

urlpatterns = [

    path('aufgabe_erstellen/', views.aufgabe_neu_erstellen, name='aufgabe_erstellen'),
    path('rechnung/', views.rechnung_view, name='rechnung'),
    path('rechnung/<int:aufgabe_id>/', views.rechnung_detail_view, name='rechnung_detail'),
    path('zufaellige_aufgabe_zuweisen/<int:aufgabe_id>/', views.zufaellige_aufgabe_zuweisen, name='zufaellige_aufgabe_zuweisen'),
    path('unternehmen_verwalten/', views.unternehmen_verwalten, name='unternehmen_verwalten'),
    path('unternehmen_loeschen/<int:unternehmen_id>/', views.unternehmen_loeschen, name='unternehmen_loeschen'),
    path('aufgabenkategorie_verwalten/', views.aufgabenkategorie_verwalten, name='aufgabenkategorie_verwalten'),
    path('aufgabenkategorie_loeschen/<int:kategorie_id>/', views.aufgabenkategorie_loeschen, name='aufgabenkategorie_loeschen'),
    path('hauptbuch/', views.hauptbuch, name='hauptbuch'),
    path('aufgabe_bearbeiten/<int:aufgabe_id>/', views.aufgabe_bearbeiten, name='aufgabe_bearbeiten'),
    path('aufgabe_loeschen/<int:aufgabe_id>/', views.aufgabe_loeschen, name='aufgabe_loeschen'),
    path('korrekturbuchung_durchfuehren/<int:buchung_id>/', views.korrekturbuchung_durchfuehren, name='korrekturbuchung_durchfuehren'),
    path('posteingang/', views.posteingang, name='posteingang'),
    path('mail/<int:mail_id>/', views.mail_detail, name='mail_detail'),
    path('konten_verwalten/', views.konten_verwalten, name='konten_verwalten'),
    path("konto_bearbeiten/<int:konto_id>/", views.konto_bearbeiten, name="konto_bearbeiten"),
    path('konto_loeschen/<int:konto_id>/', views.konto_loeschen, name='konto_loeschen'),
    path('nutzer_fortschritt/', views.nutzer_fortschritt, name='nutzer_fortschritt'),
    path('lehrer_fortschritt/', views.lehrer_fortschritt, name='lehrer_fortschritt'),
    path('lehrer_filter_daten/', views.lehrer_filter_daten, name='lehrer_filter_daten'),
    path('lehrer_studi_fortschritt/<int:student_id>/', views.lehrer_studi_fortschritt, name='lehrer_studi_fortschritt'),
    path('guv/', views.guv_uebersicht, name='guv_uebersicht'),

]