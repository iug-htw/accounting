from django.shortcuts import render, redirect 
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm 
from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm, StudiengangForm, SemesterForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.http import HttpResponse
from .models import Studiengang, Semester, CustomUser
from posts.views import lehrkraft_required
from posts.models import Mail
from django.contrib import messages
from posts.views import generiere_zufaellige_werte, speichere_nutzer_aufgabe, berechne_naechsten_versuch, erstelle_aufgaben_mail
from posts.views import Aufgabe_neu
from django.core.mail import send_mail
from django.conf import settings

@login_required  # Ensure only logged-in users can access this view
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
            if "next" in request.POST:
                return redirect(request.POST.get('next'))
            else: 
                return redirect("frontpage")
        return redirect("frontpage")
    else:
        form = AuthenticationForm()
    return render(request, "users/login.html", { "form": form })

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

@lehrkraft_required
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

@lehrkraft_required
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
                display_name=student_name
            )
            student.set_password(student_name)  # Passwort richtig hashen
            student.save()

            # Erstelle interne Nachricht statt E-Mail zu senden
            send_profile_update_mail(student)

            neue_studierende.append(student)

        if fehlgeschlagene_namen:
            messages.error(request, f"Folgende Namen sind bereits vergeben: {', '.join(fehlgeschlagene_namen)}")
        else:
            messages.success(request, f'{len(neue_studierende)} Studierende erfolgreich erstellt.')

        return redirect('users:bulk_student_creation')

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

    aufgaben = Aufgabe_neu.objects.all()
    semester = Semester.objects.all()
    studiengaenge = Studiengang.objects.all()

    if request.method == 'POST':
        ausgewählte_aufgaben = request.POST.getlist('aufgaben')
        ausgewählte_semester = request.POST.getlist('semester')
        ausgewählte_studiengaenge = request.POST.getlist('studiengaenge')

        # Studierende filtern, die den Kriterien entsprechen
        studierende = CustomUser.objects.filter(
            role='student',
            semester__id__in=ausgewählte_semester,
            studiengang__id__in=ausgewählte_studiengaenge
        )

        for aufgabe_id in ausgewählte_aufgaben:
            aufgabe = Aufgabe_neu.objects.get(id=aufgabe_id)
            for student in studierende:
                zufaellige_werte = generiere_zufaellige_werte(aufgabe)
                speichere_nutzer_aufgabe(student, aufgabe, zufaellige_werte)
                naechster_versuch = berechne_naechsten_versuch(student, aufgabe)
                erstelle_aufgaben_mail(student, aufgabe, naechster_versuch)

        messages.success(request, "Aufgaben erfolgreich zugewiesen und Mails verschickt.")
        return redirect('users:aufgaben_zuweisen')

    return render(request, 'users/aufgaben_zuweisen.html', {
        'aufgaben': aufgaben,
        'semester': semester,
        'studiengaenge': studiengaenge
    })


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
            print(mail.id)
            if mail:
                mail.status = "bearbeitet"
                mail.save(update_fields=["status"])

            return redirect("users:update_profile")

        messages.warning(request, "Keine Änderungen vorgenommen.")

    return render(request, "users/update_profile.html", {"user": user})


def send_profile_update_mail(user):
    """Erstellt eine interne Mail für den Nutzer zur Aufforderung, Namen & Passwort zu ändern."""
    Mail.objects.create(
        nutzer=user,
        aufgabe=None,  # Diese Mail ist nicht auf eine Aufgabe bezogen
        betreff="Bitte aktualisieren Sie Ihren Anzeigenamen & Ihr Passwort",
        mailtext=f"""
        Hallo {user.username},

        Bitte setzen Sie Ihren Anzeigenamen und Ihr Passwort über den folgenden Link:
        <a href='/users/update-profile/'>Profil aktualisieren</a>

        Vielen Dank!
        """,
        versuch=1,  # Standardversuch
        status="nicht bearbeitet"
    )
