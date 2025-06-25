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
from posts.models import Mail, NutzerAufgabe, Absender, Unternehmen
from django.contrib import messages
from posts.views import generiere_zufaellige_werte, speichere_nutzer_aufgabe, berechne_naechsten_versuch, erstelle_aufgaben_mail
from posts.views import Aufgabe_neu
from django.core.mail import send_mail
from django.conf import settings
import random
from django.db.models import Q
from collections import defaultdict
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

ORGA_MAILS = [
    {
        "betreff": "Personalanfrage: Neue Mitarbeitende einstellen",
        "betreff_de": "Personalanfrage: Neue Mitarbeitende einstellen",
        "betreff_en": "Staffing request: Hiring new employees",
        "mailtext": "Sehr geehrte Geschäftsführung,<br><br> unser Unternehmen verzeichnet aktuell ein starkes Wachstum in den Bereichen Vertrieb und Entwicklung. Um diesem Trend gerecht zu werden, möchten wir die Besetzung von zwei neuen Positionen prüfen: einen Junior-Vertriebsmitarbeiter und eine Middle-Level-Softwareentwicklerin. Die Anforderungsprofile wurden bereits erstellt und an die Personalabteilung weitergeleitet, die kurzfristig mit der Kandidatensuche beginnt.<br> Bitte genehmigen Sie die zusätzlichen Stellen und das geplante Budget, damit wir den Auswahlprozess schnellstmöglich starten können.<br><br> Mit freundlichen Grüßen<br> Ihr HR-Team",
        "mailtext_de": "Sehr geehrte Geschäftsführung,<br><br> unser Unternehmen verzeichnet aktuell ein starkes Wachstum in den Bereichen Vertrieb und Entwicklung. Um diesem Trend gerecht zu werden, möchten wir die Besetzung von zwei neuen Positionen prüfen: einen Junior-Vertriebsmitarbeiter und eine Middle-Level-Softwareentwicklerin. Die Anforderungsprofile wurden bereits erstellt und an die Personalabteilung weitergeleitet, die kurzfristig mit der Kandidatensuche beginnt.<br> Bitte genehmigen Sie die zusätzlichen Stellen und das geplante Budget, damit wir den Auswahlprozess schnellstmöglich starten können.<br><br> Mit freundlichen Grüßen<br> Ihr HR-Team",
        "mailtext_en": "Dear Management,<br><br> our company is currently experiencing strong growth in both sales and development. To support this expansion, we propose staffing two new positions: a junior sales representative and a mid-level software engineer. Job descriptions have already been finalized and forwarded to HR, which will commence candidate sourcing immediately.<br> Please approve the additional headcount and budget so we can initiate the recruitment process as soon as possible.<br><br> Best regards,<br> Your HR Team"
    },
    {
        "betreff": "Neue Werbekampagne geplant – Agenturfreigabe erforderlich",
        "betreff_de": "Neue Werbekampagne geplant – Agenturfreigabe erforderlich",
        "betreff_en": "Planned new advertising campaign – agency approval required",
        "mailtext": "Liebe Geschäftsführung,<br><br>unser Marketing-Team hat eine neue, integrierte Kampagne für den Herbst geplant, die Social-Media-Ads, Bannerwerbung und gezielte E-Mail-Aktionen umfasst. Um den Zeitplan einhalten zu können, benötigt die beauftragte Agentur Ihre Freigabe bis spätestens Ende der Woche.<br><br>Bitte bestätigen Sie kurzfristig die Freigabe der Kampagne und des zugehörigen Budgets. Die Agentur steht für Rückfragen jederzeit bereit und freut sich auf Ihre Rückmeldung.<br><br>Ihr Marketing-Team",
        "mailtext_de": "Liebe Geschäftsführung,<br><br>unser Marketing-Team hat eine neue, integrierte Kampagne für den Herbst geplant, die Social-Media-Ads, Bannerwerbung und gezielte E-Mail-Aktionen umfasst. Um den Zeitplan einhalten zu können, benötigt die beauftragte Agentur Ihre Freigabe bis spätestens Ende der Woche.<br><br>Bitte bestätigen Sie kurzfristig die Freigabe der Kampagne und des zugehörigen Budgets. Die Agentur steht für Rückfragen jederzeit bereit und freut sich auf Ihre Rückmeldung.<br><br>Ihr Marketing-Team",
        "mailtext_en": "Dear Management,<br><br>our marketing team has planned a new integrated campaign for the autumn, including social media ads, display banners, and targeted email promotions. To stay on schedule, the appointed agency requires your approval by the end of this week.<br><br>Please confirm the campaign and associated budget release at your earliest convenience. The agency is available for any questions and looks forward to your feedback.<br><br>Your Marketing Team",
    },
    {
        "betreff": "Geplante IT-Wartung – Zustimmung erforderlich",
        "betreff_de": "Geplante IT-Wartung – Zustimmung erforderlich",
        "betreff_en": "Planned IT maintenance – approval required",
        "mailtext": "Guten Tag,<br><br>unsere IT-Abteilung plant am 2. Juli 2025 ein umfassendes Serverupdate, um dringend erforderliche Sicherheits-Patches einzuspielen und die Systemstabilität weiter zu optimieren. Für das Update ist eine kurze Downtime von höchstens zwei Stunden außerhalb der Hauptarbeitszeit vorgesehen. Vorab werden vollständige Backups erstellt und Testläufe in unserer Staging-Umgebung durchgeführt, um einen reibungslosen Ablauf sicherzustellen.<br><br>Bitte genehmigen Sie diese Wartungsmaßnahme und das vorgeschlagene Zeitfenster, damit wir mit den Vorbereitungen beginnen können.<br><br>Ihre IT-Abteilung",
        "mailtext_de": "Guten Tag,<br><br>unsere IT-Abteilung plant am 2. Juli 2025 ein umfassendes Serverupdate, um dringend erforderliche Sicherheits-Patches einzuspielen und die Systemstabilität weiter zu optimieren. Für das Update ist eine kurze Downtime von höchstens zwei Stunden außerhalb der Hauptarbeitszeit vorgesehen. Vorab werden vollständige Backups erstellt und Testläufe in unserer Staging-Umgebung durchgeführt, um einen reibungslosen Ablauf sicherzustellen.<br><br>Bitte genehmigen Sie diese Wartungsmaßnahme und das vorgeschlagene Zeitfenster, damit wir mit den Vorbereitungen beginnen können.<br><br>Ihre IT-Abteilung",
        "mailtext_en": "Dear Management,<br><br>our IT department has scheduled a comprehensive server update on July 2, 2025, to apply critical security patches and further enhance system stability. The update will require a brief downtime of no more than two hours during off-peak hours. Prior to the maintenance window, full backups will be taken and test runs will be conducted in our staging environment to ensure a smooth process.<br><br>Please approve this maintenance activity and the proposed time slot so we can commence preparations.<br><br>Your IT Department",
    } 
]

@lehrkraft_required  # Ensure only logged-in users can access this view
def register_view(request):
    if not request.user.role == 'teacher':  # Only teachers can create students
        link = reverse("index")
        text = _('Fehlende Berechtigung') + f'<br><a href="{link}">{_("Zurück zur Startseite")}</a>'
        return HttpResponse(text)
    
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
            messages.error(request, _("Benutzername oder Passwort ist nicht korrekt."))
    
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
            studiengang = form.save(commit=False)
            studiengang.ersteller = request.user.id
            form.save()
            return redirect('users:add_studiengang')
    else:
        form = StudiengangForm()
    
    # Alle Studiengänge abrufen
    studiengaenge = Studiengang.objects.filter(
        Q(ersteller=request.user.id) | Q(ersteller=1)
    )

    return render(request, 'users/add_studiengang.html', {
        'form': form,
        'studiengaenge': studiengaenge
    })

@lehrkraft_required
def delete_studiengang_view(request, studiengang_id):
    studiengang = Studiengang.objects.get(id=studiengang_id)
    # Berechtigung prüfen
    if studiengang.ersteller and studiengang.ersteller != request.user.id and not request.user.is_superuser:
        return HttpResponse(_('Keine Berechtigung zum Löschen.'))
    studiengang.delete()
    return redirect('users:add_studiengang')

@lehrkraft_required
def add_semester_view(request):
    if request.method == 'POST':
        form = SemesterForm(request.POST)
        if form.is_valid():
            semester = form.save(commit=False)
            semester.ersteller = request.user.id
            form.save()
            messages.success(request, _("Semester erfolgreich hinzugefügt."))
            return redirect('users:add_semester')
    else:
        form = SemesterForm()

    semester = Semester.objects.filter(
        Q(ersteller=request.user.id) | Q(ersteller=1)
    )
    return render(request, 'users/add_semester.html', {
        'form': form,
        'semester': semester
    })

@lehrkraft_required
def delete_semester_view(request, semester_id):
    semester = Semester.objects.get(id=semester_id)
    if semester.ersteller and semester.ersteller != request.user.id and not request.user.is_superuser:
        return HttpResponse(_('Keine Berechtigung zum Löschen.'))
    semester.delete()
    messages.success(request, _("Semester erfolgreich gelöscht."))
    return redirect('users:add_semester')

@lehrkraft_required
def bulk_student_creation(request):
    if request.method == 'POST':
        anzahl_studierende = int(request.POST.get('anzahl_studierende', 1))
        studiengang = request.POST.get('studiengang')
        semester = request.POST.get('semester')
        name_mode = request.POST.get('name_mode')
        custom_name = request.POST.get('custom_name', "").strip()
        unternehmen_id = request.POST.get('unternehmen')
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
                unternehmen_id=unternehmen_id
            )
            student.set_password(student_name)  # Passwort richtig hashen
            student.save()
            send_willkommen_mail(student)
            send_profile_update_mail(student, request)
            neue_studierende.append(student)

        if fehlgeschlagene_namen:
            message = _("Folgende Namen sind bereits vergeben: %(namen)s") % {
                "namen": ", ".join(fehlgeschlagene_namen)
            }
            messages.error(request, message)
        else:
            message = _("%(anzahl)d Studierende erfolgreich erstellt.") % {
                "anzahl": len(neue_studierende)
            }
            messages.success(request, message)
        unternehmen = Unternehmen.objects.all()
        return render(request, 'users/bulk_student_creation.html', {
            'studiengaenge': Studiengang.objects.all(),
            'semester': Semester.objects.all(),
            'unternehmen': Unternehmen.objects.all(),
            'neue_studierende': neue_studierende,
            'fehlgeschlagene_namen': fehlgeschlagene_namen,
            'unternehmen': unternehmen,
        })

    studiengaenge = Studiengang.objects.filter(
    Q(ersteller=request.user.id) | Q(ersteller=1)
    )
    semester = Semester.objects.filter(
        Q(ersteller=request.user.id) | Q(ersteller=1)
    )
    unternehmen = Unternehmen.objects.filter(
        Q(ersteller=request.user.id) | Q(ersteller=1)
    )
    return render(request, 'users/bulk_student_creation.html', {
        'studiengaenge': studiengaenge,
        'semester': semester,
        'unternehmen': unternehmen,
    })


@lehrkraft_required
def aufgaben_zuweisen_view(request):

    # Eigene Studierenden filtern
    eigene_studierende = CustomUser.objects.filter(professor=request.user, role='student')

    # Eigene Semester und Studiengänge
    eigene_semester = Semester.objects.filter(id__in=eigene_studierende.values_list('semester_id', flat=True).distinct())
    eigene_studiengaenge = Studiengang.objects.filter(id__in=eigene_studierende.values_list('studiengang_id', flat=True).distinct())

    alle_aufgaben = Aufgabe_neu.objects.filter(
        Q(ersteller=request.user.id) | Q(ersteller=1)
    )
    # Normale Aufgaben (ohne Fallstudie)
    normale_aufgaben = alle_aufgaben.filter(unternehmen_kategorie__isnull=True).order_by('id')
    # Fallstudien Aufgaben: Sicher gruppiert
    fallstudien_aufgaben = defaultdict(list)
    for aufgabe in alle_aufgaben.filter(unternehmen_kategorie__isnull=False).select_related('unternehmen_kategorie').order_by('unternehmen_kategorie__name', 'id'):
        if aufgabe.unternehmen_kategorie:
            fallstudien_aufgaben[aufgabe.unternehmen_kategorie.name].append(aufgabe)

    fallstudien_aufgaben = dict(fallstudien_aufgaben)  # wichtig fürs Template!

    # Übersicht: Aufgaben pro Semester und Studiengang
    aufgaben_uebersicht = {}
    for sem in eigene_semester:
        aufgaben_uebersicht[sem.name] = {}
        for studiengang in eigene_studiengaenge:
            studis_in_gruppe = eigene_studierende.filter(semester=sem, studiengang=studiengang)
            # Aufgaben nach ID sortieren
            zugewiesene_aufgaben = Aufgabe_neu.objects.filter(nutzeraufgabe__nutzer__in=studis_in_gruppe).order_by('id').distinct()
            if zugewiesene_aufgaben.exists():
                aufgaben_uebersicht[sem.name][studiengang.name] = list(zugewiesene_aufgaben)
    # Aufgaben zuweisen
    if request.method == 'POST':
        if 'alle_zuweisen' in request.POST:
            return aufgaben_selbst_zuweisen(request)
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
                if NutzerAufgabe.objects.filter(nutzer=student, aufgabe=aufgabe).exists():
                    continue  # Aufgabe bereits zugewiesen – überspringen
                zufaellige_werte = generiere_zufaellige_werte(aufgabe)
                nutzer_aufgabe = speichere_nutzer_aufgabe(student, aufgabe, zufaellige_werte)
                #print(f"Hier steht der Absender in User{nutzer_aufgabe.absender_id}")
                naechster_versuch = berechne_naechsten_versuch(student, aufgabe)
                erstelle_aufgaben_mail(student, aufgabe, naechster_versuch,nutzer_aufgabe.absender)
                sende_orga_mail_wenn_noetig(student)

        messages.success(request, _("Aufgaben erfolgreich zugewiesen."))
        return redirect('users:aufgaben_zuweisen')

    return render(request, 'users/aufgaben_zuweisen.html', {
        'normale_aufgaben': normale_aufgaben,
        'fallstudien_aufgaben': fallstudien_aufgaben,
        'semester': eigene_semester,
        'studiengaenge': eigene_studiengaenge,
        'aufgaben_uebersicht': aufgaben_uebersicht
    })

@lehrkraft_required
def aufgaben_selbst_zuweisen(request):
    """Weist dem Lehrer alle Aufgaben selbst zu."""
    lehrer = request.user
    
    # Alle zugehörigen Daten zu den NutzerAufgaben löschen
    nutzer_aufgaben = NutzerAufgabe.objects.filter(nutzer=lehrer)
    aufgaben_ids = nutzer_aufgaben.values_list('id', flat=True)
    # Zugehörige Mails löschen
    Mail.objects.filter(nutzer=lehrer).exclude(aufgabe__isnull=True).delete()
    
    # Zugehörige Absender löschen
    Absender.objects.filter(id__in=nutzer_aufgaben.values_list('absender_id', flat=True)).delete()
    
    # NutzerAufgaben löschen
    nutzer_aufgaben.delete()
    
    
    aufgaben = Aufgabe_neu.objects.filter(
        Q(ersteller=lehrer.id) | Q(ersteller=1)
    )
    print(f"Es wurden {aufgaben.count()} Aufgaben gefunden.")
    for aufgabe in aufgaben:
        print(f"Verarbeite Aufgabe {aufgabe.id}")
    for aufgabe in aufgaben:
        zufaellige_werte = generiere_zufaellige_werte(aufgabe)
        print(f"zufaellige_werte: {zufaellige_werte}")
        nutzer_aufgabe = speichere_nutzer_aufgabe(lehrer, aufgabe, zufaellige_werte)
        naechster_versuch = berechne_naechsten_versuch(lehrer, aufgabe)
        erstelle_aufgaben_mail(lehrer, aufgabe, naechster_versuch, nutzer_aufgabe.absender)

    messages.success(request, _("Alle Aufgaben wurden dir erfolgreich zugewiesen."))
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
                messages.error(request, _("Passwörter stimmen nicht überein."))
                return redirect("users:update_profile")

        if name_geändert or passwort_geändert:
            user.save()
            messages.success(request, _("Profil erfolgreich aktualisiert."))

            # Älteste Mail des Nutzers ohne Aufgabe als bearbeitet markieren
            mail = Mail.objects.filter(nutzer=user, aufgabe__isnull=True).order_by("datum")[1]
            #rint(mail.id)
            if mail:
                mail.status = "bearbeitet"
                mail.save(update_fields=["status"])

            return redirect("users:update_profile")

        messages.warning(request, _("Keine Änderungen vorgenommen."))

    return render(request, "users/update_profile.html", {"user": user})


def send_profile_update_mail(user, request):
    """Erstellt eine interne Mail für den Nutzer zur Aufforderung, Namen & Passwort zu ändern."""
    update_profile_url = request.build_absolute_uri(reverse("users:update_profile"))
    absender, _ = Absender.objects.get_or_create(
            name="SecureNet", email="info@securenet.de",
            straße="Treskowallee 8", stadt="Berlin", plz="10318"
        )
    betreff="Bitte aktualisieren Sie Ihren Anzeigenamen & Ihr Passwort"
    betreff_en="Please update your displayed name and your password"
    mailtext="""
        Hallo {username},

        <p>Bitte setzen Sie Ihren Anzeigenamen und Ihr Passwort über den folgenden Link:</p>

        <p><a href="{update_profile_url}">Profil aktualisieren</a></p>

        <p>Vielen Dank!</p>
        """.format(username=user.username, update_profile_url=update_profile_url)
    mailtext_en="""
        Hello {username},

        <p>Please set your password and your display name with the following link:</p>

        <p><a href="{update_profile_url}">Update profile</a></p>

        <p>Thank your!</p>
        """.format(username=user.username, update_profile_url=update_profile_url)
    Mail.objects.create(
        nutzer=user,
        aufgabe=None,  # Diese Mail ist nicht auf eine Aufgabe bezogen
        betreff=betreff,
        betreff_de=betreff,
        betreff_en=betreff_en,
        mailtext=mailtext,
        mailtext_de = mailtext,
        mailtext_en=mailtext_en,
        versuch=1,  # Standardversuch
        status = "nicht bearbeitet",
        absender=absender,
        
    )

def send_willkommen_mail(user):
    if settings.DEBUG:
        dokumentation_link = "http://localhost:8000/media/nutzerdokumentation.pdf"
    else:
        dokumentation_link = "https://train.f4.htw-berlin.de/media/nutzerdokumentation.pdf"
    absender, _ = Absender.objects.get_or_create(
            name="SecureNet", email="info@securenet.de",
            straße="Treskowallee 8", stadt="Berlin", plz="10318"
        )
    betreff="Willkommen bei SecureNet"
    betreff_en="Welcome to SecureNet"
    mailtext="""
        Hallo, <br>

        willkommen bei SecureNet! Als CEO deines Cyber-Security-Startups ist es deine Aufgabe, nicht nur dein Unternehmen mit Schwachstellenanalysen und Penetrationstests vor Angriffen zu schützen, sondern auch die Buchhaltung professionell zu führen. <br><br> \n

        Im Posteingang findest du alle wichtigen Rechnungen und Aufgaben, die du bearbeiten musst. Dein Hauptbuch bietet dir eine transparente Übersicht über alle T-Konten, damit du jederzeit nachvollziehen kannst, welche Buchungen vorgenommen wurden. Die Rechnungsübersicht hilft dir, offene und bereits bearbeitete Rechnungen im Blick zu behalten.<br><br>

        Damit dein Unternehmen langfristig erfolgreich bleibt, solltest du regelmäßig die Bilanz prüfen. Sie zeigt dir, ob dein Unternehmen solide finanziert ist und wie sich Vermögenswerte und Verbindlichkeiten ausgleichen.<br><br>

        Für eine Einführung in dein Unternehmen, kannst du gerne hier die Nutzerdokumentation einsehen: <br>
        <p><a href="{dokumentation_link}" target="_blank"> Nutzerdokumentation </a></p>
        <br><br>
        Starte jetzt und sorge dafür, dass deine Finanzen auf Kurs bleiben! Bei Fragen oder Unklarheiten steht dir dein Posteingang als zentrale Anlaufstelle zur Verfügung. <br>


        Viel Erfolg bei SecureNet!
        Dein SecureNet-Team
        """.format(dokumentation_link=dokumentation_link)
    mailtext_en = """
        Hello, <br>

        Welcome to SecureNet! As the CEO of your cyber security startup, it's your job not only to protect your company from attacks using vulnerability assessments and penetration tests, but also to manage the accounting professionally. <br><br> \n

        In your inbox, you'll find all important invoices and tasks you need to complete. Your general ledger gives you a transparent overview of all T-accounts, so you can always track which entries have been made. The invoice overview helps you keep an eye on open and already processed invoices.<br><br>

        To ensure your company remains successful in the long term, you should regularly review the balance sheet. It shows whether your business is on solid financial footing and how assets and liabilities balance out.<br><br>

        For an introduction to your company, feel free to check the user documentation here: <br>
        <p><a href="{dokumentation_link}" target="_blank"> User Documentation </a></p>
        <br><br>
        Start now and make sure your finances stay on track! If you have any questions or uncertainties, your inbox is your central point of contact. <br>

        Wishing you success at SecureNet!  
        Your SecureNet Team
        """.format(dokumentation_link=dokumentation_link)
    Mail.objects.create(
        nutzer=user,
        aufgabe=None,  # Diese Mail ist nicht auf eine Aufgabe bezogen
        betreff=betreff,
        betreff_de=betreff,
        betreff_en=betreff_en,
        mailtext=mailtext,
        mailtext_de=mailtext,
        mailtext_en=mailtext_en,
        versuch=0,  # Standardversuch
        status="bearbeitet",
        absender=absender
    ) 

def sende_orga_mail_wenn_noetig(student):
    if student.unternehmen.name not in  ('SecureNet', 'SecureNet_en'):
        return  # Nur für Unternehmen mit ID 1

    bereits_geschickt = Mail.objects.filter(
        nutzer=student,
        aufgabe__isnull=True,  # Orga-Mails haben keine konkrete Aufgabe
        betreff__in=[m["betreff"] for m in ORGA_MAILS]
    ).count()

    aktuelle_anzahl = NutzerAufgabe.objects.filter(nutzer=student).count()

    if bereits_geschickt < len(ORGA_MAILS) and aktuelle_anzahl >= (bereits_geschickt + 1) * 5:
        absender, _ = Absender.objects.get_or_create(
            name="SecureNet", email="info@securenet.de",
            straße="Treskowallee 8", stadt="Berlin", plz="10318"
        )
        info = ORGA_MAILS[bereits_geschickt]
        Mail.objects.create(
            nutzer=student,
            absender=absender,
            betreff=info["betreff"],
            betreff_de=info["betreff_de"],
            betreff_en=info["betreff_en"],
            mailtext=info["mailtext"],
            mailtext_de=info["mailtext_de"],
            mailtext_en=info["mailtext_en"],
            versuch=1,
            status="nicht bearbeitet"
        )

@require_POST
@login_required
def orga_mail_bestaetigen(request, mail_id):
    mail = get_object_or_404(Mail, id=mail_id, nutzer=request.user)
    if mail.aufgabe is None:
        mail.status = "bearbeitet"
        mail.save(update_fields=["status"])
        messages.success(request, _("Die organisatorische Aufgabe wurde als erledigt markiert."))
    return redirect("posts:posteingang")