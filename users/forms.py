from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Studiengang

class CustomUserCreationForm(UserCreationForm):
    semester = forms.ChoiceField(
        choices=CustomUser.SEMESTER_CHOICES,
        required=True,
        label="Semester"
    )
    studiengang = forms.ModelChoiceField(
        queryset=Studiengang.objects.all(),
        required=True,
        label="Studiengang"
    )

    class Meta:
        model = CustomUser
        fields = ('username',)  # Include any fields you want for user creation

 
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        professor = cleaned_data.get('professor')

        # If the user is a student, a professor must be assigned
        if role == 'student' and not professor:
            raise forms.ValidationError('Students must be assigned a teacher.')


class StudiengangForm(forms.ModelForm):
    class Meta:
        model = Studiengang
        fields = ['name']
        labels = {'name': 'Studiengang Name'}