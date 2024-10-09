from django import forms 
from . import models
from .models import Aufgabe

class CreatePost(forms.ModelForm):
    class Meta:
        model = models.Post
        fields = ['title', 'body', 'slug', 'banner']

class AufgabeForm(forms.ModelForm):
    class Meta:
        model = Aufgabe
        fields = ['kategorie', 'aufgabentext']