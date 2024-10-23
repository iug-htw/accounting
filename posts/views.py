from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from .models import Aufgabe, Kategorie
from .forms import AufgabeForm, KategorieForm
from django.contrib import messages
#from django.core.exceptions import PermissionDenied
import json, random
from django.urls import reverse
from django.http import HttpResponse
#funktional 11;17

@login_required(login_url="/users/login/")
def buchung_uebersicht_view(request):
    return render(request, 'posts/buchung_uebersicht.html')


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
        return handle_kategorie_post(request)
    else:
        return render_kategorie_form(request)

def handle_kategorie_post(request):
    form = KategorieForm(request.POST)
    if form.is_valid():
        save_kategorie(request, form)
        return redirect('posts:neue_kategorie')
    return render_kategorie_form(request)

def save_kategorie(request, form):
    kategorie = form.save(commit=False)
    kategorie.author = request.user
    kategorie.save()

def render_kategorie_form(request):
    form = KategorieForm()
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

@login_required(login_url="/users/login/")
@lehrkraft_required
def neue_aufgabe(request):
    if request.method == 'POST':
        return handle_aufgabe_post(request)
    else:
        form = AufgabeForm(user=request.user)  # Benutzer in das Formular einfügen
        return render(request, 'posts/neue_aufgabe.html', {'form': form})

def handle_aufgabe_post(request):
    form = AufgabeForm(request.POST, user=request.user)  # Benutzer in das Formular einfügen
    if form.is_valid():
        aufgabe = form.save(commit=False)
        aufgabe.author = request.user
        process_aufgabentyp(request, aufgabe)
        aufgabe.save()
        return redirect('posts:aufgaben_liste')
    return render(request, 'posts/neue_aufgabe.html', {'form': form})

def process_aufgabentyp(request, aufgabe):
    if aufgabe.aufgabentyp == 'buchungssatz':
        handle_buchungssatz(request, aufgabe)
    elif aufgabe.aufgabentyp == 'multiple_choice':
        handle_multiple_choice(request, aufgabe)
    elif aufgabe.aufgabentyp == 'texteingabe':
        handle_texteingabe(request, aufgabe)


@login_required(login_url="/users/login/")
@lehrkraft_required
def aufgaben_liste(request):
    aufgaben = Aufgabe.objects.filter(author=request.user).order_by('id')  # Aufgaben des Lehrers filtern
    return render(request, 'posts/aufgaben_liste.html', {'aufgaben': aufgaben})


@login_required(login_url="/users/login/")
def aufgabe_detail(request, aufgabe_id):
    aufgaben = get_aufgaben_for_user(request)

    if 'kategorie' in request.GET:
        aufgaben = filter_aufgaben_by_kategorie(aufgaben, request.GET.get('kategorie'))

    aufgabe = get_current_aufgabe(aufgaben, aufgabe_id)
    if not aufgabe:
        messages.error(request, "Sie sind nicht berechtigt, diese Aufgabe zu sehen.")
        return redirect('posts:buchungsaufgabe', permanent=False)

    first_aufgabe_id = get_first_aufgabe_id(aufgaben)

    loesung_soll, loesung_haben, antworten = get_loesung_and_antworten(aufgabe)

    next_id, prev_id = get_navigation_ids(aufgaben, aufgabe_id)

    return render(request, 'posts/buchungsaufgabe.html', {
        'aufgaben': aufgaben,
        'aufgabe': aufgabe,
        'loesung_soll': loesung_soll,
        'loesung_haben': loesung_haben,
        'next_id': next_id,
        'prev_id': prev_id,
        'first_aufgabe_id': first_aufgabe_id,
        'kategorie': request.GET.get('kategorie', None),
        'alle': 'alle' in request.GET,
    })

def get_aufgaben_for_user(request):
    if request.user.role == 'teacher':
        return Aufgabe.objects.filter(author=request.user).order_by('id')
    elif request.user.role == 'student':
        return Aufgabe.objects.filter(author=request.user.professor).order_by('id')
    return None

def filter_aufgaben_by_kategorie(aufgaben, kategorie_id):
    return aufgaben.filter(kategorie_id=kategorie_id).order_by('id')

def get_current_aufgabe(aufgaben, aufgabe_id):
    return aufgaben.filter(id=aufgabe_id).first()

def get_first_aufgabe_id(aufgaben):
    first_aufgabe = aufgaben.first()
    return first_aufgabe.id if first_aufgabe else None

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
    aufgabe_ids = list(aufgaben.values_list('id', flat=True))
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
        # Lehrkraft sieht nur ihre eigenen Aufgaben
        aufgaben = Aufgabe.objects.filter(author=request.user).order_by('id')
    elif request.user.role == 'student':
        # Studierende sehen nur die Buchungsaufgaben ihres Professors
        aufgaben = Aufgabe.objects.filter(author=request.user.professor).order_by('id')
    else:
        aufgaben = Aufgabe.objects.none()  # Keine Aufgaben für andere Benutzer
    return render(request, 'posts/alle_aufgaben.html', {'aufgaben': aufgaben})
