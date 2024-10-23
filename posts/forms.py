from django import forms
from .models import Aufgabe, Kategorie

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
