from django import forms
from .models import Unternehmen, Aufgabe_neu, Buchung, Aufgabenkategorie, AufgabeDetail, Konto
import json

class Aufgabe_neu_Form(forms.ModelForm):
    class Meta:
        model = Aufgabe_neu
        fields = [
            'unternehmen_kategorie',  # Jetzt automatisch als Dropdown gerendert
            'rechnungstyp',
            'fragentyp',
            'fragentyp_text',
            'mailtext',
            'frage',
            'bezugswert',
            'feedback_konto_falsch',
            'feedback_betrag_falsch',
            'min_wert',
            'max_wert',
            'nutzungsdauer',
        ]

class BuchungForm(forms.ModelForm):
    class Meta:
        model = Buchung
        fields = ['antwort_konten_soll', 'antwort_konten_haben', 'antwort_betrag_soll', 'antwort_betrag_haben']

    def clean(self):
        cleaned_data = super().clean()
        try:
            cleaned_data['antwort_konten_soll'] = json.loads(self.data.get('antwort_konten_soll') or '[]')
            cleaned_data['antwort_konten_haben'] = json.loads(self.data.get('antwort_konten_haben') or '[]')
            cleaned_data['antwort_betrag_soll'] = json.loads(self.data.get('antwort_betrag_soll') or '[]')
            cleaned_data['antwort_betrag_haben'] = json.loads(self.data.get('antwort_betrag_haben') or '[]')
        except json.JSONDecodeError:
            raise forms.ValidationError("Ungültiges JSON-Format.")
        return cleaned_data
    
class UnternehmenForm(forms.ModelForm):
    class Meta:
        model = Unternehmen
        fields = ['name']

class AufgabenkategorieForm(forms.ModelForm):
    class Meta:
        model = Aufgabenkategorie
        fields = ['name']

class AufgabeBearbeitenForm(forms.ModelForm):
    class Meta:
        model = Aufgabe_neu
        fields = ['unternehmen_kategorie', 'fragentyp', 'fragentyp_text', 'mailtext', 'frage', 'bezugswert', 'min_wert', 'max_wert', 'nutzungsdauer', 'feedback_konto_falsch', 'feedback_betrag_falsch']

class AufgabeDetailBearbeitenForm(forms.ModelForm):
    class Meta:
        model = AufgabeDetail
        fields = ['kontoname', 'soll_haben', 'betrag', 'monatsangabe', 'monat']

class KontoForm(forms.ModelForm):
    class Meta:
        model = Konto
        fields = ['name', 'kategorie', 'unterkategorie']  # NEUE FELDER HINZUGEFÜGT

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Abhängig von der Hauptkategorie (Bestandskonto/Erfolgskonto) sollen nur passende Unterkategorien angezeigt werden
        self.fields['unterkategorie'].queryset = Konto.objects.none()

        if 'kategorie' in self.data:
            try:
                kategorie = self.data.get('kategorie')
                if kategorie == "Bestandskonto":
                    self.fields['unterkategorie'].choices = [('Aktiva', 'Aktiva'), ('Passiva', 'Passiva')]
                elif kategorie == "Erfolgskonto":
                    self.fields['unterkategorie'].choices = [('Aufwand', 'Aufwand'), ('Ertrag', 'Ertrag')]
            except (ValueError, TypeError):
                pass  # Falls falsche Werte eingegeben wurden, bleibt die Auswahl leer
