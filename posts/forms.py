from django import forms
from .models import Unternehmen, Aufgabe_neu, Buchung, Aufgabenkategorie, AufgabeDetail, Konto, Kontenplan
import json
from django.db.models import Q

class Aufgabe_neu_Form(forms.ModelForm):
    kontenplan = forms.ModelChoiceField(
        queryset=Kontenplan.objects.none(),  # Erst später im __init__ dynamisch setzen
        label="Kontenplan",
        required=True
    )
    aufgabeninfo = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Zusatzinformation zur Aufgabe"
    )
    class Meta:
        model = Aufgabe_neu
        fields = [
            'unternehmen_kategorie', 
            'rechnungstyp',
            'fragentyp',
            'unterkategorie',
            'aufgabeninfo',
            'fragentyp_text',
            'mailtext',
            'feedback_konto_falsch',
            'feedback_betrag_falsch',
            'nutzungsdauer',
            'rechnungsnummer',
            'zahlweise',
            'beschreibung',
            'verabschiedung'
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['kontenplan'].queryset = Kontenplan.objects.filter(Q(id=1) | Q(nutzer=user))
            neue_reihenfolge = ['kontenplan'] + [f for f in self.fields if f != 'kontenplan']
            self.order_fields(neue_reihenfolge)

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
        fields = ['name','kontenplan','fallstudie']

class AufgabenkategorieForm(forms.ModelForm):
    class Meta:
        model = Aufgabenkategorie
        fields = ['name']

class AufgabeImportForm(forms.ModelForm):
    kontenplan = forms.ModelChoiceField(
        queryset=Kontenplan.objects.none(),
        label="Kontenplan",
        required=True
    )
    aufgabeninfo = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Zusatzinformation zur Aufgabe"
    )
    class Meta:
        model = Aufgabe_neu
        exclude = [
            'rechnungstyp', 'fragentyp', 'unterkategorie', 'fragentyp_text', 
            'nutzungsdauer', 'zahlweise', 'beschreibung', 'verabschiedung', 
            'rechnungsbetrag', 'frage', 'rechnungsnummer'
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['kontenplan'].queryset = Kontenplan.objects.filter(Q(id=1) | Q(nutzer=user))
            neue_reihenfolge = ['kontenplan'] + [f for f in self.fields if f != 'kontenplan']
            self.order_fields(neue_reihenfolge)


class AufgabeBearbeitenForm(forms.ModelForm):
    class Meta:
        model = Aufgabe_neu
        fields = ['unternehmen_kategorie', 'fragentyp', 'fragentyp_text', 'rechnungstyp','mailtext','verabschiedung','nutzungsdauer','beschreibung', 'feedback_konto_falsch', 'feedback_betrag_falsch','zahlweise']

class AufgabeDetailBearbeitenForm(forms.ModelForm):
    class Meta:
        model = AufgabeDetail
        fields = ['konto', 'soll_haben', 'betrag', 'monatsangabe', 'monat']

class KontoForm(forms.ModelForm):
    class Meta:
        model = Konto
        fields = ['name', 'kategorie', 'unterkategorie', 'kontenplan','kontonummer', 'bilanzposition_nummer']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['kontenplan'].queryset = Kontenplan.objects.all()
        self.fields['kontenplan'].label = "Kontenplan"

        if 'kategorie' in self.data:
            kategorie = self.data.get('kategorie')
            if kategorie == "Bestandskonto":
                self.fields['unterkategorie'].choices = [('Aktiva', 'Aktiva'), ('Passiva', 'Passiva')]
            elif kategorie == "Erfolgskonto":
                self.fields['unterkategorie'].choices = [('Aufwand', 'Aufwand'), ('Ertrag', 'Ertrag')]
