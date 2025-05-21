from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
import json

class Unternehmen(models.Model):
    name = models.CharField(max_length=100)
    kontenplan = models.ForeignKey('Kontenplan', on_delete=models.CASCADE)
    fallstudie = models.BooleanField(default=0)
    ersteller = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

class Aufgabenkategorie(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Absender(models.Model):
    name = models.CharField(max_length=100,null=True)
    email = models.EmailField(max_length=100,null=True)
    straße = models.CharField(max_length=255,null=True)
    stadt = models.CharField(max_length=100,null=True)
    plz = models.CharField(max_length=10,null=True)
    telnr = models.IntegerField(null=True)

    def __str__(self):
        return f"{self.name}, {self.straße}, {self.plz} {self.stadt}"


class Aufgabe_neu(models.Model):
    RECHNUNGSTYPEN = [
        ('eingehend', 'Eingehende Rechnung'),
        ('ausgehend', 'Ausgehende Rechnung'),
        ('intern', 'Interner Vorgang'),
    ]
    unternehmen_kategorie = models.ForeignKey(Unternehmen, on_delete=models.CASCADE)
    fragentyp = models.ForeignKey(Aufgabenkategorie,null=True, on_delete=models.CASCADE)
    ersteller = models.IntegerField(null=True, blank=True)
    unterkategorie = models.IntegerField(null = True, blank=True, default = 1)
    fragentyp_text = models.CharField(null = True,max_length=255)
    mailtext = models.TextField()
    frage = models.TextField(null=True,default="Dieses Feld kann gelöscht werden")
    nutzungsdauer = models.IntegerField(null=True, blank=True)
    feedback_konto_falsch = models.TextField(null=True, blank=True, help_text="Feedback, wenn ein falsches Konto gewählt wurde.")
    feedback_betrag_falsch = models.TextField(null=True, blank=True, help_text="Feedback, wenn der Betrag falsch ist.")

    #anschrift_kunde = models.TextField(blank=True, null=True, default='Kunde XYZ\nMusterstraße 1\n12345 Musterstadt')
    eigene_ansicht = models.TextField(blank=True, null=True, default='Secure Net\nTreskowallee 8\n10318 Berlin')
    rechnungsnummer = models.CharField(max_length=50, blank=True, null=True, default='RE-00001')
    datum = models.DateField(blank=True, null=True, auto_now_add=True)
    rechnungsbetrag = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=0.00)
    zahlweise = models.CharField(max_length=255, blank=True, null=True)
    verabschiedung = models.TextField(blank=True, null=True, default='Mit freundlichen Grüßen\nIhr Unternehmen')
    kontakt = models.TextField(blank=True, null=True, default='Tel: 01234 567890\nE-Mail: info@unternehmen.de')
    beschreibung = models.TextField(blank=True, null=True, default='Keine weiteren Details angegeben.')
    rechnungstyp = models.CharField(max_length=20, choices=RECHNUNGSTYPEN, default='intern')
    aufgabeninfo = models.TextField(null=True, blank=True, help_text="Optionaler Informationstext zur Aufgabe (HTML erlaubt).")
    

    def __str__(self):
        return f"{self.frage} ({self.fragentyp})"

class AufgabeDetail(models.Model):
    aufgabe = models.ForeignKey(Aufgabe_neu, on_delete=models.CASCADE, related_name="details")
    konto = models.ForeignKey('Konto', on_delete=models.CASCADE,null=True,)
    soll_haben = models.CharField(max_length=50, choices=[("Soll", "Soll"), ("Haben", "Haben")])
    betrag = models.FloatField(null=True, blank=True)  # Kann leer sein, wenn es berechnet wird
    monatsangabe = models.BooleanField(default=False)
    monat = models.IntegerField(null=True, blank=True)
    bezugs_konto_alt = models.CharField(max_length=255, null=True, blank=True)
    kontenplan = models.ForeignKey('Kontenplan', null=True, blank=True, on_delete=models.SET_NULL)
    festbetrag = models.FloatField(null=True, blank=True, help_text="Fester Betrag, falls kein Bezugskonto genutzt wird")
    bezugs_konto = models.ForeignKey('Konto',on_delete=models.SET_NULL,null=True,blank=True,related_name='verwendet_als_bezug')
    faktor = models.FloatField(null=True, blank=True, help_text="Multiplikationsfaktor, falls abhängig von einem anderen Konto")
    bilanzposition = models.IntegerField(null=True,)
    formel_typ = models.CharField(
        max_length=50,
        choices=[("faktor", "Multiplikation mit Faktor"), ("fix", "Fester Betrag"), ("summe", "Summe aus mehreren Konten")],
        default="fix"
    )

    def berechne_betrag(self):
        """ Berechnet den Betrag anhand der gespeicherten Formel. """
        if self.formel_typ == "fix" and self.festbetrag is not None:
            return self.festbetrag  # Fester Betrag bleibt unverändert
        
        elif self.formel_typ == "faktor" and self.bezugs_konten.exists():
            # Falls das Konto von einem anderen Konto abhängig ist, berechne Betrag mit Faktor
            referenz_konto = self.bezugs_konten.first()  # Erstes Bezugs-Konto nehmen (falls es mehrere gibt)
            if referenz_konto:
                return referenz_konto.berechne_betrag() * self.faktor  # Berechnung mit Faktor

        elif self.formel_typ == "summe" and self.bezugs_konten.exists():
            # Falls es eine Summe aus mehreren Konten ist, berechne die Summe
            gesamt_betrag = sum(konto.berechne_betrag() for konto in self.bezugs_konten.all())
            return gesamt_betrag  # Summe bleibt unverändert

        return self.betrag if self.betrag else 0  # Falls keine Logik zutrifft, nutze originalen Betrag

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
    original_konten_soll = models.JSONField(null=True, blank=True)
    original_konten_haben = models.JSONField(null=True, blank=True)
    korrekturbuchung = models.BooleanField(default=False)
    konto_korrekt = models.IntegerField(choices=KORREKT_CHOICES, default=0)  # 0=Richtig, 1=Soll falsch, 2=Haben falsch, 3=Beide falsch
    betrag_korrekt = models.IntegerField(choices=KORREKT_CHOICES, default=True)  # True=Richtig, False=Falsch
    feedback_ollama = models.TextField(null=True, blank=True)
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

    aufgabe = models.ForeignKey('Aufgabe_neu', on_delete=models.CASCADE)
    absender = models.ForeignKey(Absender, on_delete=models.CASCADE, null=True, blank=True)  # Neu
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    soll_konten = models.JSONField(default=list)  # Liste der Soll-Konten
    haben_konten = models.JSONField(default=list)  # Liste der Haben-Konten
    soll_betraege = models.JSONField(default=list)  # Liste der Soll-Beträge
    haben_betraege = models.JSONField(default=list)  # Liste der Haben-Beträge
    erstellt_am = models.DateTimeField(auto_now_add=True)
    bearbeitungsstand = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offen')

    def __str__(self):
        return f"NutzerAufgabe für {self.nutzer.username} - {self.aufgabe.fragentyp_text}"

    
class Mail(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    aufgabe = models.ForeignKey(Aufgabe_neu, on_delete=models.CASCADE, null=True, blank=True)
    absender = models.ForeignKey(Absender, on_delete=models.CASCADE, null=True, blank=True)  # Neu
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

    name = models.CharField(max_length=255)
    kategorie = models.CharField(max_length=20, choices=KATEGORIE_CHOICES, blank=True, null=True)
    unterkategorie = models.CharField(max_length=20, choices=UNTERKATEGORIE_CHOICES, blank=True, null=True)
    kontonummer = models.IntegerField(null=True, blank=True)
    bilanzposition_nummer = models.IntegerField(null=True, blank=True)
    eins = models.CharField(max_length=20, choices=UNTERKATEGORIE_CHOICES, blank=True, null=True)
    erstellt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, help_text="Nutzer, der das Konto erstellt hat"
    )
    kontenplan = models.ForeignKey('Kontenplan', null=True, blank=True, on_delete=models.SET_NULL)    
    def __str__(self):
        return f"{self.name} ({self.kategorie} - {self.unterkategorie})"

class Kontenplan(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return f"Kontenplan {self.id} von {self.nutzer.username}"

class Anfangsbestand(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="anfangsbestaende")
    konto = models.ForeignKey(Konto, on_delete=models.CASCADE, related_name="anfangsbestaende")
    betrag = models.FloatField()

    class Meta:
        unique_together = ("nutzer", "konto")  # Jeder Nutzer hat für jedes Konto genau einen Eintrag

    def __str__(self):
        return f"{self.nutzer.username} - {self.konto.name}: {self.betrag} €"
