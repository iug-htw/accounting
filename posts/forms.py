from django import forms 
from . import models

class CreatePost(forms.ModelForm):
    class Meta:
        model = models.Post
        fields = ['title', 'body', 'slug', 'banner']

class FormA(forms.Form):
    zahl1 = forms.IntegerField(label='Zahl 1')
    zahl2 = forms.IntegerField(label='Zahl 2')

class FormB(forms.Form):
    zahl1 = forms.IntegerField(label='Zahl 1')
    zahl2 = forms.IntegerField(label='Zahl 2')