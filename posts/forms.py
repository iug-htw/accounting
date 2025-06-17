from django import forms
from .models import Unternehmen, Aufgabe_neu, Buchung, Aufgabenkategorie, AufgabeDetail, Konto, Kontenplan
import json
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Aufgabe_neu_Form(forms.ModelForm):
    kontenplan = forms.ModelChoiceField(
        queryset=Kontenplan.objects.none(),  # Erst später im __init__ dynamisch setzen
        label=_("Kontenplan"),
        required=True,
        help_text=_("Wähle den Kontenplan aus, auf den sich diese Aufgabe bezieht.")
    )
    aufgabeninfo = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label=_("Zusatzinformation zur Aufgabe"),
        help_text=_("Optionaler Informationstext zur Aufgabe (HTML erlaubt).")
    )
    class Meta:
        model = Aufgabe_neu
        fields = [
            'kontenplan',
            'unternehmen_kategorie', 
            'fragentyp',
            'unterkategorie',
            'aufgabeninfo',
            'mailtext',
            'umsatzsteuerfrei',
            'feedback_konto_falsch',
            'feedback_betrag_falsch',
            'zahlweise',
            'beschreibung',
            'verabschiedung'
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['kontenplan'].queryset = Kontenplan.objects.filter(
                Q(nutzer=user) | Q(nutzer__is_superuser=True)
            )
            neue_reihenfolge = ['kontenplan'] + [f for f in self.fields if f != 'kontenplan']
            self.order_fields(neue_reihenfolge)
            self.fields['unternehmen_kategorie'].queryset = Unternehmen.objects.filter(
                Q(ersteller=user.id) | Q(ersteller=1)
            )

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
        label=_("Kontenplan"),
        required=True,
        help_text=_("Wähle den Kontenplan aus, auf den sich diese Aufgabe bezieht.")
    )
    aufgabeninfo = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label=_("Zusatzinformation zur Aufgabe")
    )
    class Meta:
        model = Aufgabe_neu
        fields = [
            'kontenplan',
            'unternehmen_kategorie', 
            'mailtext',
            'feedback_konto_falsch',
            'feedback_betrag_falsch',
            'eigene_ansicht',
            'kontakt',
            'aufgabeninfo'
        ]
        exclude = [
            'rechnungstyp', 'fragentyp', 'unterkategorie', 'fragentyp_text', 
            'nutzungsdauer', 'zahlweise', 'beschreibung', 'verabschiedung', 
            'rechnungsbetrag', 'rechnungsnummer', 'ersteller','immer_feedback'
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['kontenplan'].queryset = Kontenplan.objects.filter(
                Q(nutzer=user) | Q(nutzer__is_superuser=True)
            )
            neue_reihenfolge = ['kontenplan'] + [f for f in self.fields if f != 'kontenplan']
            self.order_fields(neue_reihenfolge)


class AufgabeBearbeitenForm(forms.ModelForm):
    class Meta:
        model = Aufgabe_neu
        fields = ['unternehmen_kategorie', 'fragentyp', 'fragentyp_text', 'rechnungstyp','mailtext','verabschiedung','nutzungsdauer','rechnungsnummer','umsatzsteuerfrei','beschreibung', 'feedback_konto_falsch', 'feedback_betrag_falsch','zahlweise']
    

class AufgabeDetailBearbeitenForm(forms.ModelForm):
    class Meta:
        model = AufgabeDetail
        fields = ['konto', 'soll_haben', 'betrag']
    def __init__(self, *args, **kwargs):
        kontenplan = kwargs.pop('kontenplan', None)
        super().__init__(*args, **kwargs)
        if kontenplan:
            self.fields['konto'].queryset = Konto.objects.filter(kontenplan=kontenplan)
class KontoForm(forms.ModelForm):
    class Meta:
        model = Konto
        fields = ['name', 'kategorie', 'unterkategorie', 'kontenplan','kontonummer', 'bilanzposition_nummer']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if 'kategorie' in self.data:
            kategorie = self.data.get('kategorie')
            if kategorie == "Bestandskonto":
                self.fields['unterkategorie'].choices = [('Aktiva', 'Aktiva'), ('Passiva', 'Passiva')]
            elif kategorie == "Erfolgskonto":
                self.fields['unterkategorie'].choices = [('Aufwand', 'Aufwand'), ('Ertrag', 'Ertrag')]
        if user:
            self.fields['kontenplan'].queryset = Kontenplan.objects.filter(
                Q(nutzer=user) | Q(nutzer__is_superuser=True)
            )
