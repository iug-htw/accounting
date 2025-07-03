from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

# CustomUserAdminForm: Für zusätzliche Validierung im Admin-Panel
class CustomUserAdminForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        professor = cleaned_data.get('professor')

        # Wenn die Rolle 'student' ist, muss ein Professor zugewiesen werden
        if role == 'student' and not professor:
            raise forms.ValidationError('Studierende müssen einen Professor zugewiesen bekommen.')

        return cleaned_data

# CustomUserAdmin: Anpassung des Admin-Panels
class CustomUserAdmin(UserAdmin):
    form = CustomUserAdminForm  # Verwende das angepasste Formular

    # Felder, die im Admin-Formular angezeigt werden sollen
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'professor','nutzergruppe')}),  # Füge die Felder "role" und "professor" hinzu
    )

    # Felder, die beim Hinzufügen eines neuen Benutzers im Admin angezeigt werden
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'unternehmen','professor','nutzergruppe','semester','studiengang'),  # Hinzufügen von Rolle und Professor
        }),
    )

    # Felder, die in der Admin-Listenansicht angezeigt werden
    list_display = ('username', 'role', 'professor','last_login','nutzergruppe','semester','studiengang')
    
    # Filter, um nach bestimmten Rollen zu filtern
    list_filter = ('role',)

    # Suchfelder, um nach Nutzern zu suchen
    search_fields = ('username', 'email', 'role')

admin.site.register(CustomUser, CustomUserAdmin)
