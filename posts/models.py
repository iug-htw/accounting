from django.db import models
from django.contrib.auth.models import User

class Aufgabe(models.Model):
    kategorie = models.CharField(max_length=100)
    aufgabentext = models.TextField()
    loesung_haben = models.JSONField(blank=True, null=True)  # Optional für Buchungssätze
    loesung_soll = models.JSONField(blank=True, null=True)  # Optional für Buchungssätze
    multiple_choice_antworten = models.JSONField(blank=True, null=True)  # JSON für Multiple Choice Antworten
    richtige_antwort = models.TextField(blank=True, null=True)  # Für Texteingaben (und richtige Antwort bei MC)
    aufgabentyp = models.CharField(max_length=50, choices=[
        ('buchungssatz', 'Buchungssatz'),
        ('multiple_choice', 'Multiple Choice'),
        ('texteingabe', 'Texteingabe')
    ])
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    erstellungsdatum = models.DateTimeField(auto_now_add=True)
    id = models.AutoField(primary_key=True)

    def __str__(self):
        return f"Aufgabe {self.id}: {self.kategorie} ({self.aufgabentyp})"