from django import forms
from .models import Aufgabe, Kategorie, Aufgabe_neu, Buchung
import json

class AufgabeForm(forms.ModelForm):
    kategorie = forms.ModelChoiceField(queryset=Kategorie.objects.all(), empty_label="Kategorie wählen")

    class Meta:
        model = Aufgabe
        fields = ['kategorie', 'aufgabentext', 'aufgabentyp']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')  # Der Lehrer wird an das Formular übergeben
        super(AufgabeForm, self).__init__(*args, **kwargs)
        # Kategorienauswahl auf die Kategorien des Lehrers beschränken
        self.fields['kategorie'].queryset = Kategorie.objects.filter(author=user)

class KategorieForm(forms.ModelForm):
    class Meta:
        model = Kategorie
        fields = ['name']

class Aufgabe_neu_Form(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Hole den Benutzer aus den Keyword-Argumenten
        super().__init__(*args, **kwargs)
    
    class Meta:
        model = Aufgabe_neu
        fields = [
            'unternehmen_kategorie',
            'fragentyp',
            'fragentyp_text',
            'mailtext',
            'frage',
            'bezugswert',
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