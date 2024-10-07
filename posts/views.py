from django.shortcuts import render,redirect
from .models import Post
from django.contrib.auth.decorators import login_required
from . import forms
from posts.forms import AddForm, MultiplyForm 

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
    if request.method == 'POST':
        # Hier kannst du die Logik hinzufügen, um die Eingaben des Nutzers zu verarbeiten
        soll_konten = request.POST.getlist('soll_konten[]')
        haben_konten = request.POST.getlist('haben_konten[]')
        soll_betraege = request.POST.getlist('soll_betraege[]')
        haben_betraege = request.POST.getlist('haben_betraege[]')

        # Überprüfen der Eingaben und ggf. Fehlermeldungen oder Bestätigung
        if validierung_der_buchung(soll_konten, haben_konten, soll_betraege, haben_betraege):
            # Erfolg, weiter mit der Buchung
            pass
        else:
            # Fehlermeldung an den Nutzer weitergeben
            pass
    
    return render(request, 'posts/buchungsaufgabe.html')

def validierung_der_buchung(soll_konten, haben_konten, soll_betraege, haben_betraege):
    # Hier kommt die Logik zur Überprüfung der Buchung
    return True
    