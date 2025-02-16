from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
import json

class Unternehmen(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Aufgabenkategorie(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Aufgabe_neu(models.Model):
    unternehmen_kategorie = models.ForeignKey(Unternehmen, on_delete=models.CASCADE)
    fragentyp = models.ForeignKey(Aufgabenkategorie, on_delete=models.CASCADE)
    fragentyp_text = models.CharField(max_length=255)
    mailtext = models.TextField()
    frage = models.TextField()
    bezugswert = models.FloatField()
    min_wert = models.FloatField(null=True, blank=True)
    max_wert = models.FloatField(null=True, blank=True)
    nutzungsdauer = models.IntegerField(null=True, blank=True)
    feedback_konto_falsch = models.TextField(null=True, blank=True, help_text="Feedback, wenn ein falsches Konto gewählt wurde.")
    feedback_betrag_falsch = models.TextField(null=True, blank=True, help_text="Feedback, wenn der Betrag falsch ist.")

    def __str__(self):
        return f"{self.frage} ({self.fragentyp})"


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
    STATUS_CHOICES = [
        ('offen', 'Offen'),
        ('bearbeitet', 'Bearbeitet'),
        ('korrekt', 'Korrekt'),
    ]
    KORREKT_CHOICES = [
        (0, "Richtig"),
        (1, "Soll ist falsch"),
        (2, "Haben ist falsch"),
        (3, "Beide sind falsch"),
    ]
    buchung_id = models.AutoField(primary_key=True)
    aufgabe = models.ForeignKey('Aufgabe_neu', on_delete=models.CASCADE)
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ersteller = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='ersteller')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offen')
    freischaltung = models.DateField(null=True, blank=True)
    versuch = models.PositiveIntegerField(default=1)  # Zählt die Versuche
    abgeschlossen_datum = models.DateField(null=True, blank=True)
    antwort_konten_soll = models.JSONField(null=True, blank=True)
    antwort_konten_haben = models.JSONField(null=True, blank=True)
    antwort_betrag_soll = models.JSONField(null=True, blank=True)
    antwort_betrag_haben = models.JSONField(null=True, blank=True)
    korrekturbuchung = models.BooleanField(default=False)
    konto_korrekt = models.IntegerField(choices=KORREKT_CHOICES, default=0)  # 0=Richtig, 1=Soll falsch, 2=Haben falsch, 3=Beide falsch
    betrag_korrekt = models.IntegerField(choices=KORREKT_CHOICES, default=True)  # True=Richtig, False=Falsch
    def save(self, *args, **kwargs):
        if not self.versuch:
            # Wenn kein Versuch angegeben ist, den nächsten automatisch ermitteln
            letzte_buchung = Buchung.objects.filter(aufgabe=self.aufgabe, nutzer=self.nutzer).order_by('-versuch').first()
            self.versuch = (letzte_buchung.versuch + 1) if letzte_buchung else 1
        self.antwort_konten_soll = self.antwort_konten_soll or []
        self.antwort_konten_haben = self.antwort_konten_haben or []
        self.antwort_betrag_soll = self.antwort_betrag_soll or []
        self.antwort_betrag_haben = self.antwort_betrag_haben or []
        super(Buchung, self).save(*args, **kwargs)

    def __str__(self):
        return f"Buchung {self.buchung_id} für Aufgabe {self.aufgabe.id} von Nutzer {self.nutzer.username}"

class NutzerAufgabe(models.Model):
    STATUS_CHOICES = [
        ('offen', 'Offen'),
        ('bearbeitet', 'Bearbeitet'),
        ('korrekt', 'Korrekt'),
    ]

    aufgabe = models.ForeignKey(Aufgabe_neu, on_delete=models.CASCADE)
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    soll_konto = models.CharField(max_length=255)
    haben_konto = models.CharField(max_length=255)
    betrag = models.FloatField()
    erstellt_am = models.DateTimeField(auto_now_add=True)
    bearbeitungsstand = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offen')  # Neues Feld

    def __str__(self):
        return f"NutzerAufgabe für {self.nutzer.username} - {self.aufgabe.fragentyp_text}"
    
class Mail(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    aufgabe = models.ForeignKey(Aufgabe_neu, on_delete=models.CASCADE, null=True, blank=True)
    betreff = models.CharField(max_length=255)
    mailtext = models.TextField()
    versuch = models.PositiveIntegerField(default=1)
    von = models.CharField(max_length=100, default="system@secure-net.de")
    absender_name = models.CharField(max_length=100, default="")  # Neuer Name
    absender_adresse = models.CharField(max_length=255, default="")  # Neue Adresse
    datum = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=[
        ('nicht bearbeitet', 'Nicht bearbeitet'),
        ('bearbeitet', 'Bearbeitet')
    ], default='nicht bearbeitet')

    def __str__(self):
        return f"Mail an {self.nutzer.username}: {self.betreff}"


class Konto(models.Model):
    KATEGORIE_CHOICES = [
        ('Bestandskonto', 'Bestandskonto'),
        ('Erfolgskonto', 'Erfolgskonto'),
    ]

    UNTERKATEGORIE_CHOICES = [
        ('Aktiva', 'Aktiva'),
        ('Passiva', 'Passiva'),
        ('Aufwand', 'Aufwand'),
        ('Ertrag', 'Ertrag'),
    ]

    name = models.CharField(max_length=255, unique=True)
    kategorie = models.CharField(max_length=20, choices=KATEGORIE_CHOICES, blank=True, null=True)
    unterkategorie = models.CharField(max_length=20, choices=UNTERKATEGORIE_CHOICES, blank=True, null=True)
    eins = models.CharField(max_length=20, choices=UNTERKATEGORIE_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.kategorie} - {self.unterkategorie})"

class Anfangsbestand(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="anfangsbestaende")
    konto = models.ForeignKey(Konto, on_delete=models.CASCADE, related_name="anfangsbestaende")
    betrag = models.FloatField()

    class Meta:
        unique_together = ("nutzer", "konto")  # Jeder Nutzer hat für jedes Konto genau einen Eintrag

    def __str__(self):
        return f"{self.nutzer.username} - {self.konto.name}: {self.betrag} €"
