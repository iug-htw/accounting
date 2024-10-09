from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Post(models.Model):
    title = models.CharField(max_length=75)
    body = models.TextField()
    slug = models.SlugField()
    date = models.DateTimeField(auto_now_add=True)
    banner = models.ImageField(default='fallback.png', blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, default=None)

    def __str__(self):
        return self.title
    
class Aufgabe(models.Model):
    kategorie = models.CharField(max_length=100)  # Textfeld für die Kategorie
    aufgabentext = models.TextField()  # Längeres Textfeld für den Aufgabentext
    loesung_haben = models.JSONField()  # JSON-Feld für die Lösung Haben
    loesung_soll = models.JSONField()  # JSON-Feld für die Lösung Soll
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # Verweis auf den Ersteller
    erstellungsdatum = models.DateTimeField(auto_now_add=True)  # Automatisch das aktuelle Datum hinzufügen
    id = models.AutoField(primary_key=True)  # Automatische ID, die hochgezählt wird

    def __str__(self):
        return f"Aufgabe {self.id}: {self.kategorie}"