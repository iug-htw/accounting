from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Aufgabe, Kategorie
from django.contrib.auth import get_user_model
from django.test import Client

CustomUser = get_user_model()

class UserCreationTestCase(TestCase):
    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='lehrer1', 
            password='test12345', 
            role='teacher'
        )
        self.student = CustomUser.objects.create_user(
            username='student1', 
            password='test12345', 
            role='student',
            professor=self.teacher
        )
        self.client = Client()

    def test_teacher_creation(self):
        teacher = CustomUser.objects.create_user(
            username='lehrer2', 
            password='test12345', 
            role='teacher'
        )
        self.assertEqual(teacher.role, 'teacher')

    def test_student_creation(self):
        student = CustomUser.objects.create_user(
            username='student2', 
            password='test12345', 
            role='student', 
            professor=self.teacher
        )
        self.assertEqual(student.role, 'student')
        self.assertEqual(student.professor, self.teacher)

class LinkTestCase(TestCase):
    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='lehrer1', 
            password='test12345', 
            role='teacher'
        )
        self.student = CustomUser.objects.create_user(
            username='student1', 
            password='test12345', 
            role='student',
            professor=self.teacher
        )

    def test_buchung_uebersicht_link(self):
        self.client.login(username='lehrer1', password='test12345')
        response = self.client.get(reverse('posts:buchung_uebersicht'))
        self.assertEqual(response.status_code, 200)

    def test_buchungsaufgabe_link(self):
        self.client.login(username='lehrer1', password='test12345')
        response = self.client.get(reverse('posts:buchungsaufgabe'))
        self.assertEqual(response.status_code, 200)

    def test_neue_aufgabe_link(self):
        self.client.login(username='lehrer1', password='test12345')
        response = self.client.get(reverse('posts:neue_aufgabe'))
        self.assertEqual(response.status_code, 200)

    def test_neue_kategorie_link(self):
        self.client.login(username='lehrer1', password='test12345')
        response = self.client.get(reverse('posts:neue_kategorie'))
        self.assertEqual(response.status_code, 200)

class AufgabeKategorieTestCase(TestCase):
    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='lehrer1', 
            password='test12345', 
            role='teacher'
        )
        self.client.login(username='lehrer1', password='test12345')

    def test_create_kategorie(self):
        response = self.client.post(reverse('posts:neue_kategorie'), {'name': 'TestKategorie'})
        self.assertEqual(response.status_code, 302)  # Redirects after successful creation
        self.assertTrue(Kategorie.objects.filter(name='TestKategorie').exists())

    def test_create_aufgabe(self):
        kategorie = Kategorie.objects.create(name='TestKategorie', author=self.teacher)
        # Fügt mindestens drei Antworten hinzu, um die Validierung zu bestehen
        response = self.client.post(reverse('posts:neue_aufgabe'), {
            'kategorie': kategorie.id,
            'aufgabentext': 'Testaufgabe',
            'aufgabentyp': 'multiple_choice',
            'antwort_1': 'Antwort 1',
            'antwort_2': 'Antwort 2',
            'antwort_3': 'Antwort 3',  # Mindestens drei Antworten sind erforderlich
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Aufgabe.objects.filter(aufgabentext='Testaufgabe').exists())


class BenutzerAnsichtTestCase(TestCase):
    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='lehrer1', 
            password='test12345', 
            role='teacher'
        )
        self.student = CustomUser.objects.create_user(
            username='student1', 
            password='test12345', 
            role='student', 
            professor=self.teacher
        )
        self.client.login(username='student1', password='test12345')

    def test_professor_assignment(self):
        self.assertEqual(self.student.professor, self.teacher)  # Check if the student has the correct professor

    def test_student_sees_only_teacher_tasks(self):
        kategorie = Kategorie.objects.create(name='TestKategorie', author=self.teacher)
        Aufgabe.objects.create(kategorie=kategorie, aufgabentext='Lehrer Aufgabe', author=self.teacher, aufgabentyp='buchungssatz')

        response = self.client.get(reverse('posts:buchungsaufgabe'))
        #print(response.content)  # Zum Debuggen der Antwort
        self.assertContains(response, 'Lehrer Aufgabe')  # Student should see the teacher's task

