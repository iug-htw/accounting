from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from .models import Aufgabe, Kategorie, AufgabeStatus
from users.models import CustomUser, Studiengang, Semester
from .forms import AufgabeForm, KategorieForm
from django.contrib import messages
from django.utils import timezone
import json, random
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
#funktional 11;17

# Für Lehrkräfte
def lehrkraft_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'teacher':
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponse(f'Fehlende Berechtigung <br><a href="{reverse("index")}">Zurück zur Startseite</a>')
    return _wrapped_view_func

# Für Studierende
def student_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'student':
            return HttpResponse(f'Fehlende Berechtigung <br><a href="{reverse("index")}">Zurück zur Startseite</a>')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

def initialize_task_status(aufgabe, lehrer):
    # Finde alle Studierenden, die dem Lehrer zugeordnet sind
    students = CustomUser.objects.filter(professor=lehrer, role='student')
    for student in students:
        # Initialisiere den Status für jede Aufgabe auf 'non'
        AufgabeStatus.objects.create(
            student=student,
            aufgabe=aufgabe,
            status='non'
        )

def initialize_task_status_for_new_user(user):
    if user.role == 'student':
        # Aufgaben des zugeordneten Professors abrufen
        aufgaben = Aufgabe.objects.filter(author=user.professor)
        for aufgabe in aufgaben:
            AufgabeStatus.objects.get_or_create(
                student=user, 
                aufgabe=aufgabe, 
                defaults={'status': 'non', 'freigeschaltet': True}  # Freigeschaltet vorerst auf True setzen
            )

def update_task_status_for_study_programs(request, aufgaben_ids, studiengang_ids_raw, freigeschaltet_status, default=False):
    # Durchlaufe die kombinierten Werte von studiengang_id und semester_id
    selected_students = []
    for value in studiengang_ids_raw:
        studiengang_id, semester_id = value.split('-')
        students = CustomUser.objects.filter(
            professor=request.user,
            studiengang_id=studiengang_id,
            semester_id=semester_id
        )
        selected_students.extend(students)

        # Aktualisiere den 'freigeschaltet'-Status für die ausgewählten Aufgaben und Studenten
        AufgabeStatus.objects.filter(
            student__in=students,
            aufgabe__id__in=aufgaben_ids
        ).update(freigeschaltet=freigeschaltet_status)

    # Setze 'freigeschaltet' auf False für nicht ausgewählte Programme, falls default=False
    if not default:
        other_students = CustomUser.objects.filter(
            professor=request.user
        ).exclude(id__in=[student.id for student in selected_students])
        
        AufgabeStatus.objects.filter(
            student__in=other_students,
            aufgabe__id__in=aufgaben_ids
        ).update(freigeschaltet=False)



@login_required
@lehrkraft_required
def update_aufgabe_status_multiple(request):
    if request.method == 'POST':
        aufgaben_ids = request.POST.getlist('aufgaben_ids')
        studiengang_ids_raw = request.POST.getlist('studiengang_ids')
        action = request.POST.get('action')
        
        freigeschaltet_status = True if action == 'freischalten' else False
        # Nutze die Hilfsfunktion zur Statusaktualisierung
        update_task_status_for_study_programs(request, aufgaben_ids, studiengang_ids_raw, freigeschaltet_status)

        return redirect('posts:aufgaben_liste')
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@student_required
def update_aufgabe_status(request, aufgabe_id):
    aufgabe = Aufgabe.objects.get(id=aufgabe_id)
    status, created = AufgabeStatus.objects.get_or_create(student=request.user, aufgabe=aufgabe)
    
    # Determine if the answer is correct
    is_correct = check_answer(request, aufgabe)

    # Update the task status
    if is_correct:
        status.mark_complete()
    else:
        status.mark_pending()

    return JsonResponse({'status': status.status})


def check_answer(request, aufgabe):
    if aufgabe.aufgabentyp == 'buchungssatz':
        return check_buchungssatz(request, aufgabe)
    elif aufgabe.aufgabentyp == 'multiple_choice':
        return check_multiple_choice(request, aufgabe)
    elif aufgabe.aufgabentyp == 'texteingabe':
        return check_texteingabe(request, aufgabe)
    return False  # Standardmäßig false, wenn Aufgabentyp nicht erkannt wird

def check_buchungssatz(request, aufgabe):
    try:
        # Extrahiere die Eingaben aus dem JSON-Request-Body
        data = json.loads(request.body)
        user_soll_entries = [entry['konto'] for entry in data.get('soll', [])]
        user_soll_amounts = [entry['betrag'] for entry in data.get('soll', [])]
        user_haben_entries = [entry['konto'] for entry in data.get('haben', [])]
        user_haben_amounts = [entry['betrag'] for entry in data.get('haben', [])]
    except json.JSONDecodeError:
        user_soll_entries, user_soll_amounts, user_haben_entries, user_haben_amounts = [], [], [], []

    print('Benutzer-Eingaben Soll:', list(zip(user_soll_entries, user_soll_amounts)))
    print('Benutzer-Eingaben Haben:', list(zip(user_haben_entries, user_haben_amounts)))

    loesung_soll = json.loads(aufgabe.loesung_soll)
    loesung_haben = json.loads(aufgabe.loesung_haben)

    print('Erwartete Lösung Soll:', loesung_soll)
    print('Erwartete Lösung Haben:', loesung_haben)

    user_soll = sorted(zip(user_soll_entries, map(float, user_soll_amounts)))
    user_haben = sorted(zip(user_haben_entries, map(float, user_haben_amounts)))

    db_soll = sorted([(entry['konto'], float(entry['betrag'])) for entry in loesung_soll])
    db_haben = sorted([(entry['konto'], float(entry['betrag'])) for entry in loesung_haben])

    return user_soll == db_soll and user_haben == db_haben



def check_multiple_choice(request, aufgabe):
    try:
        # Extrahiere die Antwort aus dem JSON-Request-Body
        data = json.loads(request.body)
        user_answer = data.get('mc_answer', None)
    except json.JSONDecodeError:
        user_answer = None

    correct_answer = aufgabe.richtige_antwort

    print('Benutzer-Antwort (Multiple Choice):', user_answer)
    print('Richtige Antwort (Multiple Choice):', correct_answer)

    return user_answer == correct_answer

def check_texteingabe(request, aufgabe):
    try:
        # Versuche, die Antwort aus dem JSON-Request-Body zu laden
        data = json.loads(request.body)
        user_answer = data.get('text_answer', '').strip().lower()
    except json.JSONDecodeError:
        # Fallback, falls JSON nicht korrekt geladen wird
        user_answer = None

    correct_answer = aufgabe.richtige_antwort.strip().lower()

    print('Benutzer-Antwort:', user_answer)
    print('Richtige Antwort:', correct_answer)

    return user_answer == correct_answer


@login_required(login_url="/users/login/")
def nicht_abgeschlossene_aufgaben_view(request):
    if request.user.role == 'teacher':
        # Lehrer sieht nur seine eigenen Aufgaben
        aufgaben = Aufgabe.objects.filter(author=request.user)
    elif request.user.role == 'student':
        # Studierende sehen die Aufgaben ihres Professors
        aufgaben = Aufgabe.objects.filter(author=request.user.professor)
    
    # Finde alle Aufgaben für den Benutzer, deren Status nicht 'complete' ist
    nicht_abgeschlossene_aufgaben = []
    for aufgabe in aufgaben:
        status = AufgabeStatus.objects.filter(aufgabe=aufgabe, student=request.user).exclude(status='complete').first()
        # Füge Aufgaben mit Status 'non' oder 'pending' zur Liste hinzu
        if status and status.status in ['non', 'pending']:
            aufgabe.status_display = status.get_status_display()
            nicht_abgeschlossene_aufgaben.append(aufgabe)
        

    return render(request, 'posts/alle_aufgaben.html', {
        'aufgaben': nicht_abgeschlossene_aufgaben,
        'not_complete': True,
    })



@login_required(login_url="/users/login/")
def buchung_uebersicht_view(request):
    if request.user.role == 'teacher':
        aufgaben = Aufgabe.objects.filter(author=request.user)
    elif request.user.role == 'student':
        aufgaben = Aufgabe.objects.filter(author=request.user.professor)
    
    # Filter für nicht abgeschlossene Aufgaben mit Statusanzeige
    nicht_abgeschlossene_aufgaben = []
    for aufgabe in aufgaben:
        status = AufgabeStatus.objects.filter(aufgabe=aufgabe, student=request.user).first()
        if status and status.status != 'complete':
            aufgabe.status_display = status.get_status_display()  # Status-Attribut hinzufügen
            nicht_abgeschlossene_aufgaben.append(aufgabe)
        else:
            aufgabe.status_display = 'non'  # Standardstatus für nicht gestartete Aufgaben

    return render(request, 'posts/buchung_uebersicht.html', {
        'aufgaben': nicht_abgeschlossene_aufgaben,
    })

@login_required(login_url="/users/login/")
def buchungsaufgabe_view(request):
    if request.user.role == 'teacher':
        # Lehrkraft sieht nur ihre eigenen Aufgaben
        aufgaben = Aufgabe.objects.filter(author=request.user).order_by('id')
    elif request.user.role == 'student':
        # Studierende sehen nur die Buchungsaufgaben ihres Professors
        aufgaben = Aufgabe.objects.filter(author=request.user.professor).order_by('id')
    else:
        aufgaben = None  # Keine Aufgaben für andere Benutzer
    return render(request, 'posts/buchungsaufgabe.html', {'aufgaben': aufgaben})

@login_required(login_url="/users/login/")
@lehrkraft_required
def neue_kategorie(request):
    if request.method == 'POST':
        return process_kategorie_form(request, KategorieForm(request.POST))
    return render_kategorie_form(request)

def process_kategorie_form(request, form):
    if form.is_valid():
        kategorie = save_kategorie(request, form)
        return redirect('posts:neue_kategorie')
    return render_kategorie_form(request, form)

def save_kategorie(request, form):
    kategorie = form.save(commit=False)
    kategorie.author = request.user
    kategorie.save()
    return kategorie

def render_kategorie_form(request, form=None):
    form = form or KategorieForm()
    kategorien = Kategorie.objects.filter(author=request.user)
    return render(request, 'posts/neue_kategorie.html', {'form': form, 'kategorien': kategorien})

@login_required(login_url="/users/login/")
@lehrkraft_required
def kategorie_loeschen(request, kategorie_id):
    # Versuchen, die Kategorie zu löschen
    try:
        kategorie = Kategorie.objects.get(id=kategorie_id)
        kategorie.delete()
    except Kategorie.DoesNotExist:
        pass
    return redirect('posts:neue_kategorie')

# Separate Logik für Buchungssatz
@lehrkraft_required
def handle_buchungssatz(request, aufgabe):
    haben_konten = request.POST.getlist('haben_konto')
    haben_betraege = request.POST.getlist('haben_betrag')
    loesung_haben = []

    for konto, betrag in zip(haben_konten, haben_betraege):
        loesung_haben.append({"konto": konto, "betrag": float(betrag)})
    aufgabe.loesung_haben = json.dumps(loesung_haben)

    soll_konten = request.POST.getlist('soll_konto')
    soll_betraege = request.POST.getlist('soll_betrag')
    loesung_soll = []

    for konto, betrag in zip(soll_konten, soll_betraege):
        loesung_soll.append({"konto": konto, "betrag": float(betrag)})
    aufgabe.loesung_soll = json.dumps(loesung_soll)

# Separate Logik für Multiple-Choice-Aufgaben
@lehrkraft_required
def handle_multiple_choice(request, aufgabe):
    antworten = []
    i = 1
    while f'antwort_{i}' in request.POST:
        antworten.append(request.POST.get(f'antwort_{i}'))
        i += 1
    if len(antworten) < 3:
        raise ValueError("Es müssen mindestens drei Antworten vorhanden sein.")
    # Speichere die Antworten als Liste
    aufgabe.multiple_choice_antworten = antworten
    aufgabe.richtige_antwort = antworten[0]


# Separate Logik für Texteingabe-Aufgaben
@lehrkraft_required
def handle_texteingabe(request, aufgabe):
    aufgabe.richtige_antwort = request.POST.get('richtige_antwort')  # Richtige Antwort speichern

@lehrkraft_required
def neue_aufgabe(request):
    if request.method == 'POST':
        return handle_aufgabe_post(request)
    form = AufgabeForm(user=request.user)
    
    # Prepare study programs by semester
    studiengaenge_per_semester = {}
    for semester in Semester.objects.all():
        studiengaenge_per_semester[semester] = Studiengang.objects.filter(
            students__professor=request.user,
            students__semester=semester
        ).distinct()

    return render(request, 'posts/neue_aufgabe.html', {
        'form': form,
        'studiengaenge_per_semester': studiengaenge_per_semester
    })

def handle_aufgabe_post(request):
    form = AufgabeForm(request.POST, user=request.user)
    if form.is_valid():
        aufgabe = save_aufgabe(request, form)
        selected_studiengang_ids = request.POST.getlist('studiengang_ids')
        
        # Setze 'freigeschaltet' auf True für die ausgewählten und False für die nicht ausgewählten Studiengänge und Semester
        update_task_status_for_study_programs(request, [aufgabe.id], selected_studiengang_ids, freigeschaltet_status=True, default=False)

        return redirect('posts:aufgaben_liste')
    
    return render(request, 'posts/neue_aufgabe.html', {'form': form})

def save_aufgabe(request, form):
    aufgabe = form.save(commit=False)
    aufgabe.author = request.user
    process_aufgabentyp(request, aufgabe)  # Verarbeitet den Aufgabentyp
    aufgabe.save()

    # Initialisiere den Status für alle Studierenden des Lehrers
    initialize_task_status(aufgabe, request.user)

    return aufgabe

def process_aufgabentyp(request, aufgabe):
    if aufgabe.aufgabentyp == 'buchungssatz':
        handle_buchungssatz(request, aufgabe)
    elif aufgabe.aufgabentyp == 'multiple_choice':
        handle_multiple_choice(request, aufgabe)
    elif aufgabe.aufgabentyp == 'texteingabe':
        handle_texteingabe(request, aufgabe)


@lehrkraft_required
def aufgaben_liste(request):
    aufgaben = Aufgabe.objects.filter(author=request.user).order_by('id')
    studiengaenge_per_semester = {}

    # Organize study programs by semester
    for semester in Semester.objects.all():
        studiengaenge_per_semester[semester] = Studiengang.objects.filter(
            students__professor=request.user, students__semester=semester
        ).distinct()

    return render(request, 'posts/aufgaben_liste.html', {
        'aufgaben': aufgaben,
        'studiengaenge_per_semester': studiengaenge_per_semester
    })


@login_required(login_url="/users/login/")
def aufgabe_detail(request, aufgabe_id):
    aufgaben = get_aufgaben_for_user(request)
    # Status für jede Aufgabe setzen
    for aufgabe in aufgaben:
        status = AufgabeStatus.objects.filter(aufgabe=aufgabe, student=request.user).first()
        aufgabe.status_display = status.status if status else 'non'


    # Filterung anwenden, falls nach Kategorie oder Status gefiltert werden soll
    if 'kategorie' in request.GET:
        kategorie_id = int(request.GET['kategorie'])
        aufgaben = [a for a in aufgaben if a.kategorie_id == kategorie_id]
    
    is_not_complete = 'status' in request.GET and request.GET['status'] != 'complete'
    if is_not_complete:
        aufgaben = [a for a in aufgaben if a.status_display != 'complete']
    

    # Aktuelle Aufgabe und Navigations-IDs bestimmen
    aufgabe = get_current_aufgabe(aufgaben, aufgabe_id)
    if not aufgabe:
        messages.error(request, "Aufgabe nicht verfügbar.")
        return redirect('posts:buchung_uebersicht')
    
    next_id, prev_id = get_navigation_ids(aufgaben, aufgabe.id)
    context = prepare_aufgabe_detail_context(request, aufgaben, aufgabe)
    context.update({
        'next_id': next_id,
        'prev_id': prev_id,
        'not_complete': is_not_complete,
        'kategorie': request.GET.get('kategorie', None),
    })
    return render(request, 'posts/buchungsaufgabe.html', context)





def prepare_aufgabe_detail_context(request, aufgaben, aufgabe):
    first_aufgabe_id = get_first_aufgabe_id(aufgaben)
    loesung_soll, loesung_haben, antworten = get_loesung_and_antworten(aufgabe)
    next_id, prev_id = get_navigation_ids(aufgaben, aufgabe.id)

    return {
        'aufgaben': aufgaben,
        'aufgabe': aufgabe,
        'loesung_soll': loesung_soll,
        'loesung_haben': loesung_haben,
        'next_id': next_id,
        'prev_id': prev_id,
        'first_aufgabe_id': first_aufgabe_id,
        'kategorie': request.GET.get('kategorie', None),
        'alle': 'alle' in request.GET,
    }


def get_aufgaben_for_user(request):
    if request.user.role == 'teacher':
        return Aufgabe.objects.filter(author=request.user).order_by('id')
    elif request.user.role == 'student':
        return Aufgabe.objects.filter(author=request.user.professor).order_by('id')
    return None

def filter_aufgaben_by_kategorie(aufgaben, kategorie_id):
    return aufgaben.filter(kategorie_id=kategorie_id).order_by('id')

def get_current_aufgabe(aufgaben, aufgabe_id):
    # Durchlaufe die Aufgabenliste und finde die Aufgabe mit der passenden ID
    for aufgabe in aufgaben:
        if aufgabe.id == aufgabe_id:
            return aufgabe
    return None  # Falls keine passende Aufgabe gefunden wird

def get_first_aufgabe_id(aufgaben):
    # Überprüfen, ob die Liste nicht leer ist, und gebe die ID der ersten Aufgabe zurück
    return aufgaben[0].id if aufgaben else None


def get_loesung_and_antworten(aufgabe):
    loesung_soll, loesung_haben = None, None
    antworten = None

    if aufgabe.aufgabentyp == 'buchungssatz':
        loesung_soll = json.loads(aufgabe.loesung_soll)
        loesung_haben = json.loads(aufgabe.loesung_haben)

    elif aufgabe.aufgabentyp == 'multiple_choice':
        if isinstance(aufgabe.multiple_choice_antworten, str):
            antworten = json.loads(aufgabe.multiple_choice_antworten)
        else:
            antworten = aufgabe.multiple_choice_antworten
        random.shuffle(antworten)

    return loesung_soll, loesung_haben, antworten

def get_navigation_ids(aufgaben, aufgabe_id):
    aufgabe_ids = [aufgabe.id for aufgabe in aufgaben]  # IDs manuell aus der Liste extrahieren
    current_index = aufgabe_ids.index(aufgabe_id)
    next_id = aufgabe_ids[current_index + 1] if current_index + 1 < len(aufgabe_ids) else None
    prev_id = aufgabe_ids[current_index - 1] if current_index > 0 else None
    return next_id, prev_id


@login_required(login_url="/users/login/")
def kategorien_liste(request):
    if request.user.role == 'teacher':
        # Lehrer sieht nur seine eigenen Kategorien
        kategorien = Kategorie.objects.filter(author=request.user)
    elif request.user.role == 'student':
        # Studierende sehen die Kategorien ihres Professors
        kategorien = Kategorie.objects.filter(author=request.user.professor)
    else:
        kategorien = Kategorie.objects.none()  # Keine Kategorien für andere Rollen

    return render(request, 'posts/kategorien_liste.html', {'kategorien': kategorien})


@login_required(login_url="/users/login/")
def kategorie_aufgaben(request, kategorie_id):
    kategorie = Kategorie.objects.get(id=kategorie_id)
    aufgaben = Aufgabe.objects.filter(kategorie=kategorie).order_by('id')
    return render(request, 'posts/aufgaben_liste.html', {
        'aufgaben': aufgaben,
        'kategorie': kategorie,
    })


@login_required(login_url="/users/login/")
def alle_aufgaben(request):
    if request.user.role == 'teacher':
        # Lehrer sehen ihre eigenen Aufgaben
        aufgaben = Aufgabe.objects.filter(author=request.user).order_by('id')
    elif request.user.role == 'student':
        # Studierende sehen die Aufgaben ihres Professors
        aufgaben = Aufgabe.objects.filter(author=request.user.professor).order_by('id')
    else:
        aufgaben = Aufgabe.objects.none()  # Keine Aufgaben für andere Benutzer

    # Den Status für jede Aufgabe des aktuellen Benutzers hinzufügen
    for aufgabe in aufgaben:
        status = AufgabeStatus.objects.filter(aufgabe=aufgabe, student=request.user).first()
        if status:
            aufgabe.status_display = status.get_status_display()
        else:
            aufgabe.status_display = 'non'  # Standardstatus, wenn kein Eintrag vorhanden

    return render(request, 'posts/alle_aufgaben.html', {
        'aufgaben': aufgaben,
    })
