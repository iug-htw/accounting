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
    name = models.CharField(max_length=100)
    beschreibung = models.TextField()  # Beschreibung der Aufgabe
    soll_konten = models.JSONField()  # Richtige Soll-Konten als Liste
    haben_konten = models.JSONField()  # Richtige Haben-Konten als Liste
    soll_betraege = models.JSONField()  # Richtige Soll-Beträge als Liste
    haben_betraege = models.JSONField()  # Richtige Haben-Beträge als Liste

    def __str__(self):
        return self.name