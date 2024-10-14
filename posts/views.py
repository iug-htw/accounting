from django.shortcuts import render,redirect
from .models import Post, Aufgabe
from django.contrib.auth.decorators import login_required
from . import forms
from .models import Aufgabe
from .forms import AufgabeForm
import json

# Create your views here.
def posts_list(request):
    posts = Post.objects.all().order_by('-date')
    return render(request, 'posts/posts_list.html', {'posts': posts})

def post_page(request, slug):
    post = Post.objects.get(slug=slug)
    return render(request, 'posts/post_page.html', {'post': post})

def buchungsaufgabe(request):
    return render(request, 'posts/buchungsaufgabe.html')

@login_required(login_url="/users/login/")
def post_new(request):
    if request.method == 'POST':
        form = forms.CreatePost(request.POST, request.FILES)
        if form.is_valid():
            newpost = form.save(commit=False)
            newpost.author = request.user
            newpost.save()
            return redirect('posts:list')
    else:
        form = forms.CreatePost()
    return render(request, 'posts/post_new.html', {'form':form})

def buchungsaufgabe_view(request):
    return render(request, 'posts/buchungsaufgabe.html')


@login_required(login_url="/users/login/")
def neue_aufgabe(request):
    if request.method == 'POST':
        form = AufgabeForm(request.POST)
        if form.is_valid():
            aufgabe = form.save(commit=False)
            aufgabe.author = request.user

            # Speichere die spezifischen Daten basierend auf dem Aufgabentyp
            if aufgabe.aufgabentyp == 'buchungssatz':
                # Verarbeite die Lösung Haben
                haben_konten = request.POST.getlist('haben_konto')
                haben_betraege = request.POST.getlist('haben_betrag')
                loesung_haben = []

                # Erstelle das JSON-Array für Lösung Haben
                for konto, betrag in zip(haben_konten, haben_betraege):
                    loesung_haben.append({
                        "konto": konto,
                        "betrag": float(betrag)
                    })
                aufgabe.loesung_haben = json.dumps(loesung_haben)

                # Verarbeite die Lösung Soll
                soll_konten = request.POST.getlist('soll_konto')
                soll_betraege = request.POST.getlist('soll_betrag')
                loesung_soll = []

                # Erstelle das JSON-Array für Lösung Soll
                for konto, betrag in zip(soll_konten, soll_betraege):
                    loesung_soll.append({
                        "konto": konto,
                        "betrag": float(betrag)
                    })
                aufgabe.loesung_soll = json.dumps(loesung_soll)

            elif aufgabe.aufgabentyp == 'multiple_choice':
                antworten = [request.POST.get(f'antwort_{i}') for i in range(1, 4)]
                aufgabe.multiple_choice_antworten = antworten  # Alle Antwortmöglichkeiten speichern
                aufgabe.richtige_antwort = antworten[0]        # Die erste Antwort als richtige speichern
            elif aufgabe.aufgabentyp == 'texteingabe':
                aufgabe.richtige_antwort = request.POST.get('richtige_antwort')  # Richtige Antwort speichern

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
    # JSON-Felder für loesung_soll und loesung_haben dekodieren
    loesung_soll = json.loads(aufgabe.loesung_soll)
    loesung_haben = json.loads(aufgabe.loesung_haben)
    total_tasks = Aufgabe.objects.count()  # Get the total number of tasks
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
