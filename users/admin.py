from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'role', 'is_staff', 'is_active']
    list_filter = ['role', 'is_staff', 'is_active']

    # Hier fügst du das 'role'-Feld in den Bearbeitungsformularen hinzu
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('role', 'is_staff', 'is_active', 'groups', 'user_permissions')}),  # Hier wird das 'role'-Feld hinzugefügt
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'role', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )

# Stelle sicher, dass CustomUser mit CustomUserAdmin registriert ist
admin.site.register(CustomUser, CustomUserAdmin)
