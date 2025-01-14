from django import forms
from .models import Aufgabe, Kategorie, Aufgabe_neu

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
