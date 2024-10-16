from django.contrib import admin
from .models import Aufgabe, Kategorie
# Register your models here.
admin.site.register(Aufgabe)
admin.site.register(Kategorie)

class AufgabeAdmin(admin.ModelAdmin):
    list_display = ('id', 'kategorie', 'author', 'erstellungsdatum')
    search_fields = ('kategorie', 'aufgabentext')
    list_filter = ('kategorie', 'author', 'erstellungsdatum')