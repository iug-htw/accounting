from django.test import TestCase
from django.urls import reverse
from .models import Aufgabe, Kategorie
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class AufgabeTestCase(TestCase):
    
    def setUp(self):
        # Erstellt einen Benutzer und eine Kategorie für die Tests
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.kategorie = Kategorie.objects.create(name="Test Kategorie")
    
    def test_multiple_choice_aufgabe_wird_gespeichert(self):
        # Simuliert das Einloggen
        self.client.login(username='testuser', password='12345')

        # Simuliert die POST-Anfrage mit vier Antworten
        response = self.client.post(reverse('posts:neue_aufgabe'), {
            'kategorie': self.kategorie.id,
            'aufgabentext': 'Beispielaufgabe',
            'aufgabentyp': 'multiple_choice',
            'antwort_1': 'Antwort 1',
            'antwort_2': 'Antwort 2',
            'antwort_3': 'Antwort 3',
            'antwort_4': 'Antwort 4'
        })
        
        # Prüft, ob die Aufgabe erfolgreich erstellt wurde und korrekt gespeichert ist
        self.assertEqual(response.status_code, 302)  # Erfolgreiche Umleitung nach Speichern
        aufgabe = Aufgabe.objects.get(aufgabentext='Beispielaufgabe')
        self.assertEqual(aufgabe.multiple_choice_antworten, ['Antwort 1', 'Antwort 2', 'Antwort 3', 'Antwort 4'])
        self.assertEqual(aufgabe.richtige_antwort, 'Antwort 1')

    def test_multiple_choice_weniger_als_drei_antworten(self):
         # Simuliert das Einloggen
         self.client.login(username='testuser', password='12345')
         # Simuliert die POST-Anfrage mit nur zwei Antworten und erwartet die ValueError
         with self.assertRaises(ValueError, msg="Es müssen mindestens drei Antworten vorhanden sein."):
             self.client.post(reverse('posts:neue_aufgabe'), {
                 'kategorie': self.kategorie.id,
                 'aufgabentext': 'Beispielaufgabe mit zu wenigen Antworten',
                 'aufgabentyp': 'multiple_choice',
                 'antwort_1': 'Antwort 1',
                 'antwort_2': 'Antwort 2'
             })

    def test_dynamisch_hinzufuegte_antworten_werden_gespeichert(self):
        # Simuliert das Einloggen
        self.client.login(username='testuser', password='12345')

        # Simuliert die POST-Anfrage mit sechs Antworten (dynamisch hinzugefügt)
        response = self.client.post(reverse('posts:neue_aufgabe'), {
            'kategorie': self.kategorie.id,
            'aufgabentext': 'Beispielaufgabe mit vielen Antworten',
            'aufgabentyp': 'multiple_choice',
            'antwort_1': 'Antwort 1',
            'antwort_2': 'Antwort 2',
            'antwort_3': 'Antwort 3',
            'antwort_4': 'Antwort 4',
            'antwort_5': 'Antwort 5',
            'antwort_6': 'Antwort 6'
        })
        
        # Prüft, ob die Aufgabe mit allen Antworten erstellt wurde
        self.assertEqual(response.status_code, 302)  # Erfolgreiche Umleitung
        aufgabe = Aufgabe.objects.get(aufgabentext='Beispielaufgabe mit vielen Antworten')
        self.assertEqual(aufgabe.multiple_choice_antworten, ['Antwort 1', 'Antwort 2', 'Antwort 3', 'Antwort 4', 'Antwort 5', 'Antwort 6'])
        self.assertEqual(aufgabe.richtige_antwort, 'Antwort 1')

