from django import forms 
from . import models

class CreatePost(forms.ModelForm):
    class Meta:
        model = models.Post
        fields = ['title', 'body', 'slug', 'banner']

class AddForm(forms.Form):
    number1 = forms.IntegerField(label='Number 1')
    number2 = forms.IntegerField(label='Number 2')
    
class MultiplyForm(forms.Form):
    number1 = forms.IntegerField(label='Number 3')
    number2 = forms.IntegerField(label='Number 4')
    
class TreasureForm(forms.Form):
    name = forms.CharField(max_length=100)
    estimated_price = forms.IntegerField()