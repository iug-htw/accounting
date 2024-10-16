from django.db import models
from django.contrib.auth.models import User

class Kategorie(models.Model):
    name = models.CharField(max_length=100, unique=True)

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
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    erstellungsdatum = models.DateTimeField(auto_now_add=True)
    id = models.AutoField(primary_key=True)
