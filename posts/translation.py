from modeltranslation.translator import translator, TranslationOptions
from .models import Aufgabe_neu, Mail

class AufgabeTranslationOptions(TranslationOptions):
    fields = ('mailtext', 'verabschiedung', 'kontakt', 'beschreibung')

translator.register(Aufgabe_neu, AufgabeTranslationOptions)


class MailTranslationOptions(TranslationOptions):
    fields = ('mailtext', 'betreff')  
    
translator.register(Mail, MailTranslationOptions)