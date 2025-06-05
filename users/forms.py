from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Studiengang, Semester
from django.utils.translation import gettext_lazy as _

class CustomUserCreationForm(UserCreationForm):
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
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
        labels = {'name': _("Studiengang Name")}

class SemesterForm(forms.ModelForm):
    class Meta:
        model = Semester
        fields = ['name']
        labels = {'name': _("Semestername")}