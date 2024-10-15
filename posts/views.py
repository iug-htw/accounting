from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from .models import Aufgabe
from .forms import AufgabeForm
import json, random
#funktional 11;17

def buchungsaufgabe(request):
    return render(request, 'posts/buchungsaufgabe.html')

def buchungsaufgabe_view(request):
    return render(request, 'posts/buchungsaufgabe.html')


# Separate Logik für Buchungssatz
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
def handle_multiple_choice(request, aufgabe):
    antworten = request.POST.getlist('antwort')  # Holt die Antworten als Liste
    aufgabe.multiple_choice_antworten = json.dumps(antworten)  # Speichert sie als JSON
    aufgabe.richtige_antwort = antworten[0]  # Die erste Antwort ist korrekt


# Separate Logik für Texteingabe-Aufgaben
def handle_texteingabe(request, aufgabe):
    aufgabe.richtige_antwort = request.POST.get('richtige_antwort')  # Richtige Antwort speichern

@login_required(login_url="/users/login/")
def neue_aufgabe(request):
    if request.method == 'POST':
        form = AufgabeForm(request.POST)
        if form.is_valid():
            aufgabe = form.save(commit=False)
            aufgabe.author = request.user

            # Speichere die spezifischen Daten basierend auf dem Aufgabentyp
            if aufgabe.aufgabentyp == 'buchungssatz':
                handle_buchungssatz(request, aufgabe)
            elif aufgabe.aufgabentyp == 'multiple_choice':
                handle_multiple_choice(request, aufgabe)
            elif aufgabe.aufgabentyp == 'texteingabe':
                handle_texteingabe(request, aufgabe)

            aufgabe.save()
            return redirect('posts:aufgaben_liste')
    else:
        form = AufgabeForm()
    return render(request, 'posts/neue_aufgabe.html', {'form': form})


@login_required(login_url="/users/login/")
def aufgaben_liste(request):
    aufgaben = Aufgabe.objects.all().order_by('id')
    return render(request, 'posts/aufgaben_liste.html', {'aufgaben': aufgaben})    

@login_required(login_url="/users/login/")
def aufgabe_detail(request, aufgabe_id):
    aufgabe = Aufgabe.objects.get(id=aufgabe_id)

    if aufgabe.aufgabentyp == 'buchungssatz':
        loesung_soll = json.loads(aufgabe.loesung_soll)
        loesung_haben = json.loads(aufgabe.loesung_haben)
    else:
        loesung_soll, loesung_haben = None, None

    if aufgabe.aufgabentyp == 'multiple_choice':
        # Falls multiple_choice_antworten als String gespeichert ist, konvertiere es in eine Liste
        if isinstance(aufgabe.multiple_choice_antworten, str):
            antworten = json.loads(aufgabe.multiple_choice_antworten)
        else:
            antworten = aufgabe.multiple_choice_antworten  # Falls es schon eine Liste ist
        random.shuffle(antworten)  # Antworten mischen
    else:
        antworten = None

    total_tasks = Aufgabe.objects.count()
    next_id = aufgabe_id + 1 if aufgabe_id < total_tasks else None
    prev_id = aufgabe_id - 1 if aufgabe_id > 1 else None

    return render(request, 'posts/buchungsaufgabe.html', {
        'aufgabe': aufgabe,
        'loesung_soll': loesung_soll,
        'loesung_haben': loesung_haben,
        'next_id': next_id,
        'prev_id': prev_id,
        'total_tasks': total_tasks,
    })

