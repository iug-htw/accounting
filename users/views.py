from django.shortcuts import render, redirect 
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm 
from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm, StudiengangForm, SemesterForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.urls import reverse
from django.http import HttpResponse
from .models import Studiengang, Semester, CustomUser
from posts.views import lehrkraft_required, admin_required, student_required
from posts.models import Mail, NutzerAufgabe
from django.contrib import messages
from posts.views import generiere_zufaellige_werte, speichere_nutzer_aufgabe, berechne_naechsten_versuch, erstelle_aufgaben_mail
from posts.views import Aufgabe_neu
from django.core.mail import send_mail
from django.conf import settings
import random

@lehrkraft_required  # Ensure only logged-in users can access this view
def register_view(request):
    if not request.user.role == 'teacher':  # Only teachers can create students
        return HttpResponse(f'Fehlende Berechtigung <br><a href="{reverse("index")}">Zurück zur Startseite</a>')
    
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'student'  # Ensure the created user is always a student
            user.professor = request.user  # Automatically assign the logged-in teacher as the professor
            user.studiengang = form.cleaned_data.get('studiengang')
            user.semester = form.cleaned_data.get('semester') or Semester.objects.get(id=1)
            user.nutzergruppe = random.randint(1, 4)
            user.save()
            #login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect("frontpage")  # Redirect to a suitable page after registration
    else:
        form = CustomUserCreationForm()
    
    return render(request, "users/register.html", {"form": form}) 

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            if "next" in request.POST and request.POST.get("next"):
                return redirect(request.POST.get("next"))
            return redirect("frontpage")
        else:
            messages.error(request, "Benutzername oder Passwort ist nicht korrekt.")
    
    else:
        form = AuthenticationForm()
    
    return render(request, "users/login.html", {"form": form})

def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("frontpage")
    
@lehrkraft_required
def add_studiengang_view(request):
    if request.method == 'POST':
        form = StudiengangForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('users:add_studiengang')
    else:
        form = StudiengangForm()
    
    # Alle Studiengänge abrufen
    studiengaenge = Studiengang.objects.all()

    return render(request, 'users/add_studiengang.html', {
        'form': form,
        'studiengaenge': studiengaenge
    })

@admin_required
def delete_studiengang_view(request, studiengang_id):
    studiengang = Studiengang.objects.get(id=studiengang_id)
    studiengang.delete()
    return redirect('users:add_studiengang')

@lehrkraft_required
def add_semester_view(request):
    if request.method == 'POST':
        form = SemesterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Semester erfolgreich hinzugefügt.")
            return redirect('users:add_semester')
    else:
        form = SemesterForm()

    semester = Semester.objects.all()
    return render(request, 'users/add_semester.html', {
        'form': form,
        'semester': semester
    })

@admin_required
def delete_semester_view(request, semester_id):
    semester = Semester.objects.get(id=semester_id)
    semester.delete()
    messages.success(request, "Semester erfolgreich gelöscht.")
    return redirect('users:add_semester')

@lehrkraft_required
def bulk_student_creation(request):
    if request.method == 'POST':
        anzahl_studierende = int(request.POST.get('anzahl_studierende', 1))
        studiengang = request.POST.get('studiengang')
        semester = request.POST.get('semester')
        name_mode = request.POST.get('name_mode')
        custom_name = request.POST.get('custom_name', "").strip()

        lehrkraft = request.user.username[:2]  # Die ersten 2 Buchstaben des Lehrernamens

        existing_users = CustomUser.objects.values_list('username', flat=True)
        fehlgeschlagene_namen = []
        neue_studierende = []

        for i in range(1, anzahl_studierende + 1):
            if name_mode == "on" and custom_name:
                student_name = f"{custom_name}{i}"
            else:
                student_name = f"{studiengang}{lehrkraft}{semester}{str(i).zfill(2)}"

            if student_name in existing_users:
                fehlgeschlagene_namen.append(student_name)
                continue  # Überspringe Erstellung dieses Nutzers
            
            student = CustomUser(
                username=student_name,
                email=f"{student_name}@example.com",
                role='student',
                professor=request.user,
                semester=Semester.objects.get(name=semester),
                studiengang=Studiengang.objects.get(name=studiengang),
                display_name=student_name,
                nutzergruppe=random.randint(1,4),
                unternehmen_id=1
            )
            student.set_password(student_name)  # Passwort richtig hashen
            student.save()
            send_willkommen_mail(student)
            send_profile_update_mail(student, request)
            neue_studierende.append(student)

        if fehlgeschlagene_namen:
            messages.error(request, f"Folgende Namen sind bereits vergeben: {', '.join(fehlgeschlagene_namen)}")
        else:
            messages.success(request, f'{len(neue_studierende)} Studierende erfolgreich erstellt.')

        return render(request, 'users/bulk_student_creation.html', {
            'studiengaenge': Studiengang.objects.all(),
            'semester': Semester.objects.all(),
            'neue_studierende': neue_studierende,
            'fehlgeschlagene_namen': fehlgeschlagene_namen
        })

    studiengaenge = Studiengang.objects.all()
    semester = Semester.objects.all()
    return render(request, 'users/bulk_student_creation.html', {
        'studiengaenge': studiengaenge,
        'semester': semester
    })


@lehrkraft_required
def aufgaben_zuweisen_view(request):
    if not request.user.role == 'teacher':
        return HttpResponse(f'Fehlende Berechtigung <br><a href="/">Zurück zur Startseite</a>')

    # Eigene Studierenden filtern
    eigene_studierende = CustomUser.objects.filter(professor=request.user, role='student')

    # Eigene Semester und Studiengänge
    eigene_semester = Semester.objects.filter(id__in=eigene_studierende.values_list('semester_id', flat=True).distinct())
    eigene_studiengaenge = Studiengang.objects.filter(id__in=eigene_studierende.values_list('studiengang_id', flat=True).distinct())

    aufgaben = Aufgabe_neu.objects.all()

    # Übersicht: Aufgaben pro Semester und Studiengang
    aufgaben_uebersicht = {}
    for sem in eigene_semester:
        aufgaben_uebersicht[sem.name] = {}
        for studiengang in eigene_studiengaenge:
            studis_in_gruppe = eigene_studierende.filter(semester=sem, studiengang=studiengang)
            # Aufgaben nach ID sortieren
            zugewiesene_aufgaben = Aufgabe_neu.objects.filter(nutzeraufgabe__nutzer__in=studis_in_gruppe).order_by('id').distinct()
            if zugewiesene_aufgaben.exists():
                aufgaben_uebersicht[sem.name][studiengang.name] = [f"Aufgabe {aufgabe.id}" for aufgabe in zugewiesene_aufgaben]
    
    # Aufgaben zuweisen
    if request.method == 'POST':
        ausgewählte_aufgaben = request.POST.getlist('aufgaben')
        ausgewählte_semester = request.POST.getlist('semester')
        ausgewählte_studiengaenge = request.POST.getlist('studiengaenge')

        for aufgabe_id in ausgewählte_aufgaben:
            aufgabe = Aufgabe_neu.objects.get(id=aufgabe_id)
            studierende = eigene_studierende.filter(
                semester__id__in=ausgewählte_semester,
                studiengang__id__in=ausgewählte_studiengaenge,
                unternehmen=aufgabe.unternehmen_kategorie
            )
            for student in studierende:
                zufaellige_werte = generiere_zufaellige_werte(aufgabe)
                nutzer_aufgabe = speichere_nutzer_aufgabe(student, aufgabe, zufaellige_werte)
                print(f"Hier steht der Absender in User{nutzer_aufgabe.absender_id}")
                naechster_versuch = berechne_naechsten_versuch(student, aufgabe)
                erstelle_aufgaben_mail(student, aufgabe, naechster_versuch,nutzer_aufgabe.absender)

        messages.success(request, "Aufgaben erfolgreich zugewiesen.")
        return redirect('users:aufgaben_zuweisen')

    return render(request, 'users/aufgaben_zuweisen.html', {
        'aufgaben': aufgaben,
        'semester': eigene_semester,
        'studiengaenge': eigene_studiengaenge,
        'aufgaben_uebersicht': aufgaben_uebersicht
    })

@lehrkraft_required
def aufgaben_selbst_zuweisen(request):
    """Weist dem Lehrer alle Aufgaben selbst zu."""
    lehrer = request.user
    NutzerAufgabe.objects.filter(nutzer=lehrer).delete()
    aufgaben = Aufgabe_neu.objects.all()  # Alle Aufgaben abrufen

    for aufgabe in aufgaben:
        zufaellige_werte = generiere_zufaellige_werte(aufgabe)
        print(f"zufaellige_werte: {zufaellige_werte}")
        nutzer_aufgabe = speichere_nutzer_aufgabe(lehrer, aufgabe, zufaellige_werte)
        naechster_versuch = berechne_naechsten_versuch(lehrer, aufgabe)
        erstelle_aufgaben_mail(lehrer, aufgabe, naechster_versuch, nutzer_aufgabe.absender)

    messages.success(request, "Alle Aufgaben wurden dir erfolgreich zugewiesen.")
    return redirect('users:aufgaben_zuweisen')


@login_required
def update_profile(request):
    user = request.user
    name_geändert = False
    passwort_geändert = False

    if request.method == "POST":
        if "save_display_name" in request.POST:
            neuer_name = request.POST.get("display_name", "").strip()
            if neuer_name and neuer_name != user.display_name:
                user.display_name = neuer_name
                name_geändert = True

        if "save_password" in request.POST:
            neues_passwort = request.POST.get("password", "").strip()
            passwort_bestätigung = request.POST.get("password_confirm", "").strip()

            if neues_passwort and neues_passwort == passwort_bestätigung:
                user.set_password(neues_passwort)
                passwort_geändert = True
                update_session_auth_hash(request, user)  # Nutzer bleibt eingeloggt

            elif neues_passwort and neues_passwort != passwort_bestätigung:
                messages.error(request, "Passwörter stimmen nicht überein.")
                return redirect("users:update_profile")

        if name_geändert or passwort_geändert:
            user.save()
            messages.success(request, "Profil erfolgreich aktualisiert.")

            # Älteste Mail des Nutzers ohne Aufgabe als bearbeitet markieren
            mail = Mail.objects.filter(nutzer=user, aufgabe__isnull=True).order_by("datum").first()
            #rint(mail.id)
            if mail:
                mail.status = "bearbeitet"
                mail.save(update_fields=["status"])

            return redirect("users:update_profile")

        messages.warning(request, "Keine Änderungen vorgenommen.")

    return render(request, "users/update_profile.html", {"user": user})


def send_profile_update_mail(user, request):
    """Erstellt eine interne Mail für den Nutzer zur Aufforderung, Namen & Passwort zu ändern."""
    update_profile_url = request.build_absolute_uri(reverse("users:update_profile"))
    Mail.objects.create(
        nutzer=user,
        aufgabe=None,  # Diese Mail ist nicht auf eine Aufgabe bezogen
        betreff="Bitte aktualisieren Sie Ihren Anzeigenamen & Ihr Passwort",
        mailtext=f"""
        Hallo {user.username},

        <p>Bitte setzen Sie Ihren Anzeigenamen und Ihr Passwort über den folgenden Link:</p>

        <p><a href="{update_profile_url}">Profil aktualisieren</a></p>

        <p>Vielen Dank!</p>
        """,
        versuch=1,  # Standardversuch
        status="nicht bearbeitet"
    )

def send_willkommen_mail(user):
    Mail.objects.create(
        nutzer=user,
        aufgabe=None,  # Diese Mail ist nicht auf eine Aufgabe bezogen
        betreff="Willkommen bei SecureNet",
        mailtext=f"""
        Hallo,

        willkommen bei SecureNet! Als CEO deines Cyber-Security-Startups ist es deine Aufgabe, nicht nur dein Unternehmen mit Schwachstellenanalysen und Penetrationstests vor Angriffen zu schützen, sondern auch die Buchhaltung professionell zu führen.

        Im Posteingang findest du alle wichtigen Rechnungen und Aufgaben, die du bearbeiten musst. Dein Hauptbuch bietet dir eine transparente Übersicht über alle T-Konten, damit du jederzeit nachvollziehen kannst, welche Buchungen vorgenommen wurden. Die Rechnungsübersicht hilft dir, offene und bereits bearbeitete Rechnungen im Blick zu behalten.

        Damit dein Unternehmen langfristig erfolgreich bleibt, solltest du regelmäßig die Bilanz prüfen. Sie zeigt dir, ob dein Unternehmen solide finanziert ist und wie sich Vermögenswerte und Verbindlichkeiten ausgleichen.

        Starte jetzt und sorge dafür, dass deine Finanzen auf Kurs bleiben! Bei Fragen oder Unklarheiten steht dir dein Posteingang als zentrale Anlaufstelle zur Verfügung.

        Viel Erfolg bei SecureNet!
        Dein SecureNet-Team
        """,
        versuch=0,  # Standardversuch
        status="bearbeitet"
    )