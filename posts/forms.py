from django import forms
from .models import Aufgabe, Kategorie

class AufgabeForm(forms.ModelForm):
    kategorie = forms.ModelChoiceField(queryset=Kategorie.objects.all(), empty_label="Kategorie wählen")

    class Meta:
        model = Aufgabe
        fields = ['kategorie', 'aufgabentext', 'aufgabentyp']

class KategorieForm(forms.ModelForm):
    class Meta:
        model = Kategorie
        fields = ['name']
