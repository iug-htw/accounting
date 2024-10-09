from django.contrib import admin
from .models import Post, Aufgabe
# Register your models here.
admin.site.register(Post)
admin.site.register(Aufgabe)

class AufgabeAdmin(admin.ModelAdmin):
    list_display = ('id', 'kategorie', 'author', 'erstellungsdatum')
    search_fields = ('kategorie', 'aufgabentext')
    list_filter = ('kategorie', 'author', 'erstellungsdatum')