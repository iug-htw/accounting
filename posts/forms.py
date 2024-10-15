from django import forms 
from .models import Aufgabe
#funktional 11;17

class AufgabeForm(forms.ModelForm):
    class Meta:
        model = Aufgabe
        fields = ['kategorie', 'aufgabentext','aufgabentyp']