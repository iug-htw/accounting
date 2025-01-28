from django import forms
from .models import Unternehmen, Aufgabe_neu, Buchung, Aufgabenkategorie
import json

class Aufgabe_neu_Form(forms.ModelForm):
    unternehmen_kategorie = forms.ModelChoiceField(
        queryset=Unternehmen.objects.all(),
        required=True,
        label="Unternehmen Kategorie"
    )
    fragentyp = forms.ModelChoiceField(
        queryset=Aufgabe_neu.objects.values_list('fragentyp_text', flat=True).distinct(),
        required=True,
        label="Fragentyp"
    )

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
    
class UnternehmenForm(forms.ModelForm):
    class Meta:
        model = Unternehmen
        fields = ['name']

class AufgabenkategorieForm(forms.ModelForm):
    class Meta:
        model = Aufgabenkategorie
        fields = ['name']