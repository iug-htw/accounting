from django.urls import path, include
from . import views

app_name = 'posts'

urlpatterns = [

    path('aufgabe_erstellen/', views.aufgabe_neu_erstellen, name='aufgabe_erstellen'),
    path('rechnung/', views.rechnung_detail_view, name='rechnung'),
    path('rechnung/<int:aufgabe_id>/', views.rechnung_detail_view, name='rechnung_detail'),
    path('unternehmen_verwalten/', views.unternehmen_verwalten, name='unternehmen_verwalten'),
    path('unternehmen_loeschen/<int:unternehmen_id>/', views.unternehmen_loeschen, name='unternehmen_loeschen'),
    path('aufgabenkategorie_verwalten/', views.aufgabenkategorie_verwalten, name='aufgabenkategorie_verwalten'),
    path('aufgabenkategorie_loeschen/<int:kategorie_id>/', views.aufgabenkategorie_loeschen, name='aufgabenkategorie_loeschen'),
    path('hauptbuch/', views.hauptbuch_view, name='hauptbuch'),
    path('aufgabe_bearbeiten/<int:aufgabe_id>/', views.aufgabe_bearbeiten, name='aufgabe_bearbeiten'),
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
    path('speichere_guv_ergebnis/', views.speichere_guv_ergebnis, name='speichere_guv_ergebnis'),
    path('bilanz/', views.bilanz_uebersicht, name='bilanz'),
    path('rechnungsuebersicht/', views.rechnungsuebersicht, name='rechnungsuebersicht'),
    path('aufgaben/', views.aufgaben_verwalten, name='aufgaben_verwalten'),
    path('aufgabe/<int:aufgabe_id>/loeschen/', views.aufgabe_loeschen, name='aufgabe_loeschen'),
    path('ollama_prompt/', views.ollama_prompt_view, name='ollama_prompt'),
    path("buchungssatz-uebersicht/", views.buchungssatz_uebersicht, name="buchungssatz_uebersicht"),
    path('aufgabe_import_form/', views.aufgabe_import_form, name='aufgabe_import_form'),
    path('kontenplan_konten_laden/', views.kontenplan_konten_laden, name='kontenplan_konten_laden'),
    path('tkonto_vorschau/', views.tkonto_vorschau, name='tkonto_vorschau'),
    path('kontenplan_loeschen/<int:pk>/', views.kontenplan_loeschen, name='kontenplan_loeschen'),
    path('freie_buchung/', views.freie_buchung, name="freie_buchung"),
]