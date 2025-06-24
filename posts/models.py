from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
import json
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from datetime import date, timedelta
import random

class Unternehmen(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    kontenplan = models.ForeignKey('Kontenplan', on_delete=models.CASCADE, verbose_name=_("kontenplan"))
    fallstudie = models.BooleanField(default=0, verbose_name=_("Fallstudie"))
    ersteller = models.IntegerField(null=True, blank=True, verbose_name=_("Ersteller"))

    def __str__(self):
        return self.name

class Aufgabenkategorie(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Absender(models.Model):
    name = models.CharField(max_length=100,null=True, verbose_name=_("Name"))
    email = models.EmailField(max_length=100,null=True, verbose_name=_("Email"))
    straße = models.CharField(max_length=255,null=True, verbose_name=_("Straße"))
    stadt = models.CharField(max_length=100,null=True, verbose_name=_("Stadt"))
    plz = models.CharField(max_length=10,null=True, verbose_name=_("Plz"))
    telnr = models.IntegerField(null=True, verbose_name=_("telnr"))

    def __str__(self):
        return f"{self.name}, {self.straße}, {self.plz} {self.stadt}"


class Aufgabe_neu(models.Model):
    RECHNUNGSTYPEN = [
        ('eingehend', _('Eingehende Rechnung')),
        ('ausgehend', _('Ausgehende Rechnung')),
        ('intern', _('Interner Vorgang')),
        ('non', _('Keine Rechnungsansicht'))
    ]
    unternehmen_kategorie = models.ForeignKey(Unternehmen, on_delete=models.CASCADE,help_text="Das Unternehmen oder die Fallstudie, zu welcher die Aufgabe zugeordnet wird.", verbose_name=_("Unternehmen Kategorie"))
    fragentyp = models.ForeignKey(Aufgabenkategorie,null=True, on_delete=models.CASCADE, help_text="Der Aufgabentyp; Was für eine Art von Aufgabe liegt vor?", verbose_name=_("Fragentyp"))
    ersteller = models.IntegerField(null=True, blank=True, verbose_name=_("Ersteller"))
    unterkategorie = models.IntegerField(null = True, blank=True, default = 1,help_text="Feld für Unterteilung von Fragen mit dem selben Fragentyp", verbose_name=_("Unterkategorie"))
    fragentyp_text = models.CharField(null = True,max_length=255) #kann weg
    mailtext = models.TextField(help_text="Der angezeigte Text in der Mail, welchen die Nutzer für jede Aufgabe erhalten.", verbose_name=_("Mailtext"))
    mailtext_de = models.TextField(null=True,help_text="Der angezeigte Text in der Mail, welchen die Nutzer für jede Aufgabe erhalten.", verbose_name=_("Mailtext"))
    mailtext_en = models.TextField(null=True,help_text="Der angezeigte Text in der Mail, welchen die Nutzer für jede Aufgabe erhalten.", verbose_name=_("Mailtext"))
    nutzungsdauer = models.IntegerField(null=True, blank=True, verbose_name=_("Nutzungsdauer"))
    feedback_konto_falsch = models.TextField(null=True, blank=True, help_text="Ein allgemeines Feedback für eine falsche Lösung hinsichtlich der ausgewählten Konten.", verbose_name=_("Feedback Konto falsch"))
    feedback_betrag_falsch = models.TextField(null=True, blank=True, help_text="Ein allgemeines Feedback für eine falsche Lösung hinsichtlich des Betrages.", verbose_name=_("Feedback Betrag falsch"))
    immer_feedback = models.BooleanField(null=True, blank=True, verbose_name=_("immer Feedback"))
    #anschrift_kunde = models.TextField(blank=True, null=True, default='Kunde XYZ\nMusterstraße 1\n12345 Musterstadt')
    umsatzsteuerfrei = models.BooleanField(null=True, blank=True, default=0)
    eigene_ansicht = models.TextField(blank=True, null=True, default='SecureNet\nTreskowallee 8\n10318 Berlin',help_text="Angezeigter Text in der Mail, welche für die Nutzer verschickt wird. Zeigt die Addresse des eigenen Unternehmens", verbose_name=_("Eigene Ansicht"))
    rechnungsnummer = models.CharField(max_length=50, blank=True, null=True, default='RE-00001', verbose_name=_("Rechnungsnummer"))
    datum = models.DateField(blank=True, null=True, auto_now_add=True, verbose_name=_("Datum"))
    rechnungsbetrag = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=0.00, verbose_name=_("Rechnungsbetrag"))
    zahlweise = models.CharField(max_length=255, blank=True, null=True,help_text="Auf welche Weise wird gezahlt? (Bar, Überweisung...)", verbose_name=_("Zahlweise"))
    verabschiedung = models.TextField(blank=True, null=True, default='Mit freundlichen Grüßen\nIhr Unternehmen',help_text="Angezeigter Text in der Mail. Zeigt die Verabschiedung. ", verbose_name=_("Verabschiedung"))
    verabschiedung_de = models.TextField(blank=True, null=True, default='Mit freundlichen Grüßen\nIhr Unternehmen',help_text="Angezeigter Text in der Mail. Zeigt die Verabschiedung. ", verbose_name=_("Verabschiedung"))
    verabschiedung_en = models.TextField(blank=True, null=True, default='With regards\nYour Business',help_text="Angezeigter Text in der Mail. Zeigt die Verabschiedung. ", verbose_name=_("Verabschiedung"))
    kontakt = models.TextField(blank=True, null=True, default='Tel: 01234 567890\nE-Mail: info@unternehmen.de',help_text="Angezeigter Text in der Mail. Zeigt die Kontaktdaten des eigenen Unternehmens", verbose_name=_("Kontakt"))
    beschreibung = models.TextField(blank=True, null=True, default='Keine weiteren Details angegeben.', verbose_name=_("Beschreibung"))
    beschreibung_de = models.TextField(blank=True, null=True, default='Keine weiteren Details angegeben.', verbose_name=_("Beschreibung"))
    beschreibung_en = models.TextField(blank=True, null=True, default='No further details.', verbose_name=_("Beschreibung"))
    rechnungstyp = models.CharField(max_length=20, choices=RECHNUNGSTYPEN, default='intern', verbose_name=_("Rechnungstyp"))
    aufgabeninfo = models.TextField(null=True, blank=True, help_text="Optionaler Informationstext zur Aufgabe (HTML erlaubt).", verbose_name=_("Aufgabeninfo"))
    hat_leistungszeitraum = models.BooleanField(null=True, blank=True, default=0)

    def __str__(self):
        return f"({self.fragentyp})"

class AufgabeDetail(models.Model):
    aufgabe = models.ForeignKey(Aufgabe_neu, on_delete=models.CASCADE, related_name="details", verbose_name=_("Aufgabe"))
    konto = models.ForeignKey('Konto', on_delete=models.CASCADE,null=True, verbose_name=_("Konto"))
    soll_haben = models.CharField(max_length=50, choices=[("Soll", "Soll"), ("Haben", "Haben")], verbose_name=_("Soll/Haben"))
    betrag = models.FloatField(null=True, blank=True, verbose_name=_("Betrag"))  # Kann leer sein, wenn es berechnet wird
    kontenplan = models.ForeignKey('Kontenplan', null=True, blank=True, on_delete=models.SET_NULL,help_text="Feedback, wenn ein falsches Konto gewählt wurde.", verbose_name=_("Kontenplan"))
    bilanzposition = models.IntegerField(null=True, verbose_name=_("Bilanzposition"))

class Buchung(models.Model):
    STATUS_CHOICES = [
        ('offen', _('Offen')),
        ('bearbeitet', _('Bearbeitet')),
        ('korrekt', _('Korrekt')),
    ]
    KORREKT_CHOICES = [
        (0, _("Richtig")),
        (1, _("Soll ist falsch")),
        (2, _("Haben ist falsch")),
        (3, _("Beide sind falsch")),
    ]
    buchung_id = models.AutoField(primary_key=True, verbose_name=_("Buchungs ID"))
    aufgabe = models.ForeignKey('Aufgabe_neu', on_delete=models.CASCADE, verbose_name=_("Aufgabe"))
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Nutzer"))
    ersteller = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='ersteller', verbose_name=_("Ersteller"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offen', verbose_name=_("Status"))
    freischaltung = models.DateField(null=True, blank=True, verbose_name=_("Freischaltung"))
    versuch = models.PositiveIntegerField(default=1, verbose_name=_("Versuch"))  # Zählt die Versuche
    abgeschlossen_datum = models.DateField(null=True, blank=True, verbose_name=_("Abgeschlossen Datum"))
    antwort_konten_soll = models.JSONField(null=True, blank=True, verbose_name=_("Antwort Konten Soll"))
    antwort_konten_haben = models.JSONField(null=True, blank=True, verbose_name=_("Antwort Konten Haben"))
    antwort_betrag_soll = models.JSONField(null=True, blank=True, verbose_name=_("Antwort Betrag Soll"))
    antwort_betrag_haben = models.JSONField(null=True, blank=True, verbose_name=_("Antwort Betrag Haben"))
    original_konten_soll = models.JSONField(null=True, blank=True, verbose_name=_("Original Konten Soll"))
    original_konten_haben = models.JSONField(null=True, blank=True, verbose_name=_("Original Konten Haben"))
    korrekturbuchung = models.BooleanField(default=False, verbose_name=_("Korrekturbuchung"))
    konto_korrekt = models.IntegerField(choices=KORREKT_CHOICES, default=0, verbose_name=_("Konto Korrekt"))  # 0=Richtig, 1=Soll falsch, 2=Haben falsch, 3=Beide falsch
    betrag_korrekt = models.IntegerField(choices=KORREKT_CHOICES, default=True, verbose_name=_("Betrag Korrekt"))  # True=Richtig, False=Falsch
    feedback_ollama = models.TextField(null=True, blank=True, verbose_name=_("Feedback Ollama"))
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
        ('offen', _('Offen')),
        ('bearbeitet', _('Bearbeitet')),
        ('korrekt', _('Korrekt')),
    ]

    aufgabe = models.ForeignKey('Aufgabe_neu', on_delete=models.CASCADE, verbose_name=_("Aufgabe"))
    absender = models.ForeignKey(Absender, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Absender"))  # Neu
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Nutzer"))
    soll_konten = models.JSONField(default=list, verbose_name=_("Soll Konten"))  # Liste der Soll-Konten
    haben_konten = models.JSONField(default=list, verbose_name=_("Haben Konten"))  # Liste der Haben-Konten
    soll_betraege = models.JSONField(default=list, verbose_name=_("Soll Beträge"))  # Liste der Soll-Beträge
    haben_betraege = models.JSONField(default=list, verbose_name=_("Haben Beträge"))  # Liste der Haben-Beträge
    erstellt_am = models.DateTimeField(auto_now_add=True, verbose_name=_("Erstellt am"))
    bearbeitungsstand = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offen', verbose_name=_("Bearbeitungsstand"))
    leistungszeitraum_anfang = models.DateField(null=True, blank=True)
    leistungszeitraum_ende = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"NutzerAufgabe für {self.nutzer.username} - {self.aufgabe.fragentyp_text}"
    def speichere_leistungszeitraum(self):
        """Erzeugt einen gültigen Leistungszeitraum auf Basis der Aufgabenerstellung."""
        referenzdatum = date.today()
        # 1. Wähle Startdatum: 1–3 Monate vor Rechnungsdatum
        tage_vorher = random.randint(1, 45)
        dauer_tage = random.randint(14, 60)
        startdatum = referenzdatum - timedelta(days=tage_vorher+dauer_tage)
        endedatum = referenzdatum - timedelta(days=tage_vorher)
        # 3. Falls Jahreswechsel: kürze Enddatum auf 31.12 des Startjahres
        if endedatum.year != startdatum.year:
            endedatum = date(startdatum.year, 12, 31)
        self.leistungszeitraum_anfang = startdatum
        self.leistungszeitraum_ende = endedatum
    def save(self, *args, **kwargs):
        if not self.leistungszeitraum_anfang or not self.leistungszeitraum_ende:
            self.speichere_leistungszeitraum()
        super().save(*args, **kwargs)
    
class Mail(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Nutzer"))
    aufgabe = models.ForeignKey(Aufgabe_neu, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Aufgabe"))
    absender = models.ForeignKey(Absender, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Absender"))  # Neu
    betreff = models.CharField(max_length=255, verbose_name=_("Betreff"))
    betreff_de = models.CharField(null=True,max_length=255, verbose_name=_("Betreff"))
    betreff_en = models.CharField(null=True,max_length=255, verbose_name=_("Betreff"))
    mailtext = models.TextField(verbose_name=_("Mailtext"))
    mailtext_de = models.TextField(null=True,verbose_name=_("Mailtext"))
    mailtext_en = models.TextField(null=True,verbose_name=_("Mailtext"))
    versuch = models.PositiveIntegerField(default=1, verbose_name=_("Versuch"))
    von = models.CharField(max_length=100, default="system@secure-net.de", verbose_name=_("Von"))
    absender_name = models.CharField(max_length=100, default="", verbose_name=_("Absender Name"))  # Neuer Name
    absender_adresse = models.CharField(max_length=255, default="", verbose_name=_("Absender Adresse"))  # Neue Adresse
    datum = models.DateTimeField(auto_now_add=True, verbose_name=_("Datum"))
    status = models.CharField(max_length=50, choices=[
        ('nicht bearbeitet', _('Nicht bearbeitet')),
        ('bearbeitet', _('Bearbeitet'))
    ], default=_('nicht bearbeitet'))

    def __str__(self):
        return f"Mail an {self.nutzer.username}: {self.betreff}"


class Konto(models.Model):
    KATEGORIE_CHOICES = [
        ('Bestandskonto', _('Bestandskonto')),
        ('Erfolgskonto', _('Erfolgskonto')),
    ]

    UNTERKATEGORIE_CHOICES = [
        ('Aktiva', _('Aktiva')),
        ('Passiva', _('Passiva')),
        ('Aufwand', _('Aufwand')),
        ('Ertrag', _('Ertrag')),
    ]

    name = models.CharField(max_length=255, verbose_name=_("name"))
    kategorie = models.CharField(max_length=20, choices=KATEGORIE_CHOICES, blank=True, null=True, verbose_name=_("kategorie"))
    unterkategorie = models.CharField(max_length=20, choices=UNTERKATEGORIE_CHOICES, blank=True, null=True, verbose_name=_("Unterkategorie"))
    kontonummer = models.IntegerField(null=True, blank=True, verbose_name=_("Kontonummer"))
    bilanzposition_nummer = models.IntegerField(null=True, blank=True, verbose_name=_("Bilanzposition Nummer"))
    eins = models.CharField(max_length=20, choices=UNTERKATEGORIE_CHOICES, blank=True, null=True, verbose_name=_("eins"))
    erstellt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, help_text="Nutzer, der das Konto erstellt hat", verbose_name=_("Erstellt von")
    )
    kontenplan = models.ForeignKey('Kontenplan', null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("Kontenplan"))    
    def __str__(self):
        return f"{self.name} ({self.kategorie} - {self.unterkategorie})"

class Kontenplan(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Nutzer"))
    sprache = models.IntegerField(null=True, default = 0)
    def __str__(self):
        if self.id == 1:
            return "SecureNet"
        if self.id == 2:
            return "SecureNet_en"
        return gettext("Kontenplan %(nutzer)s (%(id)s)") % {
            "nutzer": self.nutzer.username,
            "id": self.nutzer.id
        }

class Anfangsbestand(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="anfangsbestaende", verbose_name=_("Nutzer"))
    konto = models.ForeignKey(Konto, on_delete=models.CASCADE, related_name="anfangsbestaende", verbose_name=_("Konto"))
    betrag = models.FloatField(verbose_name=_("Betrag"))

    class Meta:
        unique_together = ("nutzer", "konto")  # Jeder Nutzer hat für jedes Konto genau einen Eintrag

    def __str__(self):
        return f"{self.nutzer.username} - {self.konto.name}: {self.betrag} €"
