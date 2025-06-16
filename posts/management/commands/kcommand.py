from django.core.management.base import BaseCommand
from posts.models import Aufgabe_neu
from django.utils import translation

class Command(BaseCommand):
    help = 'Überträgt Originaltexte in _de-Felder'

    def handle(self, *args, **kwargs):
        translation.activate('en')

        for aufgabe in Aufgabe_neu.objects.all():
            original_mailtext = aufgabe.mailtext
            original_verabschiedung = aufgabe.verabschiedung
            original_kontakt = aufgabe.kontakt
            original_beschreibung = aufgabe.beschreibung

            translation.activate('de')

            aufgabe.mailtext = original_mailtext
            aufgabe.verabschiedung = original_verabschiedung
            aufgabe.kontakt = original_kontakt
            aufgabe.beschreibung = original_beschreibung

            aufgabe.save()

        translation.deactivate()
        self.stdout.write(self.style.SUCCESS('Texte erfolgreich übertragen.'))
