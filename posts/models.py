from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
import json

class Kategorie(models.Model):
    name = models.CharField(max_length=100, unique=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})

    def __str__(self):
        return self.name

class Aufgabe(models.Model):
    kategorie = models.ForeignKey(Kategorie, on_delete=models.CASCADE)  # Ändere CharField zu ForeignKey
    aufgabentext = models.TextField()
    loesung_haben = models.JSONField(blank=True, null=True)
    loesung_soll = models.JSONField(blank=True, null=True)
    multiple_choice_antworten = models.JSONField(blank=True, null=True)
    richtige_antwort = models.TextField(blank=True, null=True)
    aufgabentyp = models.CharField(max_length=50, choices=[
        ('buchungssatz', 'Buchungssatz'),
        ('multiple_choice', 'Multiple Choice'),
        ('texteingabe', 'Texteingabe')
    ])
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    erstellungsdatum = models.DateTimeField(auto_now_add=True)
    id = models.AutoField(primary_key=True)

from django.db import models
from django.conf import settings

from django.db import models
from django.conf import settings
from django.utils import timezone


class AufgabeStatus(models.Model):
    STATUS_CHOICES = [
        ('non', 'Nicht bearbeitet'),
        ('pending', 'Falsch eingereicht'),
        ('complete', 'Richtig eingereicht'),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='aufgaben_status'
    )
    aufgabe = models.ForeignKey(
        'Aufgabe', 
        on_delete=models.CASCADE,
        related_name='aufgaben_status'
    )
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='non'
    )
    date_completed = models.DateTimeField(null=True, blank=True)
    freigeschaltet = models.BooleanField(default=True)  # Neues Feld hinzugefügt

    class Meta:
        unique_together = ('student', 'aufgabe')

    def mark_complete(self):
        self.status = 'complete'
        self.date_completed = timezone.now()
        self.save()

    def mark_pending(self):
        self.status = 'pending'
        self.save()

    def __str__(self):
        return f"{self.student.username} - {self.aufgabe.id}: {self.get_status_display()}"

class Aufgabe_neu(models.Model):
    unternehmen_kategorie = models.IntegerField()
    fragentyp = models.IntegerField()
    fragentyp_text = models.CharField(max_length=255)
    mailtext = models.TextField()
    frage = models.TextField()
    bezugswert = models.FloatField()
    min_wert = models.FloatField(null=True, blank=True)
    max_wert = models.FloatField(null=True, blank=True)
    nutzungsdauer = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.frage} ({self.fragentyp_text})"

class AufgabeDetail(models.Model):
    aufgabe = models.ForeignKey(Aufgabe_neu, on_delete=models.CASCADE, related_name="details")
    kontoname = models.CharField(max_length=255)
    soll_haben = models.CharField(max_length=50, choices=[("Soll", "Soll"), ("Haben", "Haben")])
    betrag = models.FloatField()
    monatsangabe = models.BooleanField(default=False)
    monat = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.kontoname} - {self.soll_haben} - {self.betrag}"

class Buchung(models.Model):
    buchung_id = models.AutoField(primary_key=True)
    aufgabe = models.ForeignKey('Aufgabe_neu', on_delete=models.CASCADE)
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ersteller = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='ersteller')
    freischaltung = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('gelöst', 'Gelöst'),
        ('falsch', 'Falsch'),
        ('offen', 'Offen'),
    ], default='offen')
    abgeschlossen_datum = models.DateField(null=True, blank=True)
    antwort_konten_soll = models.JSONField(null=True, blank=True)
    antwort_konten_haben = models.JSONField(null=True, blank=True)
    antwort_betrag_soll = models.JSONField(null=True, blank=True)
    antwort_betrag_haben = models.JSONField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.antwort_konten_soll = self.antwort_konten_soll or []
        self.antwort_konten_haben = self.antwort_konten_haben or []
        self.antwort_betrag_soll = self.antwort_betrag_soll or []
        self.antwort_betrag_haben = self.antwort_betrag_haben or []
        super(Buchung, self).save(*args, **kwargs)

    def __str__(self):
        return f"Buchung {self.buchung_id} für Aufgabe {self.aufgabe.id} von Nutzer {self.nutzer.username}"

class NutzerAufgabe(models.Model):
    aufgabe = models.ForeignKey(Aufgabe_neu, on_delete=models.CASCADE)
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    soll_konto = models.CharField(max_length=255)  # Konto für Soll
    haben_konto = models.CharField(max_length=255)  # Konto für Haben
    betrag = models.FloatField()  # Zufälliger Betrag
    erstellt_am = models.DateTimeField(auto_now_add=True)
    geloest = models.BooleanField(default=False)

    def __str__(self):
        return f"NutzerAufgabe für {self.nutzer.username} - {self.aufgabe.fragentyp_text}"
