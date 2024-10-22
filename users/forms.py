from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role', 'professor')  # Include any fields you want for user creation


    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        professor = cleaned_data.get('professor')

        # If the user is a student, a professor must be assigned
        if role == 'student' and not professor:
            raise forms.ValidationError('Students must be assigned a professor.')
