from django.shortcuts import render,redirect
from .models import Post, Aufgabe
from django.contrib.auth.decorators import login_required
from . import forms
from .forms import AufgabeForm

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


@login_required
def neue_aufgabe(request):
    if request.method == 'POST':
        form = AufgabeForm(request.POST)
        if form.is_valid():
            aufgabe = form.save(commit=False)
            aufgabe.author = request.user  # Der aktuelle Benutzer wird als Autor gespeichert
            aufgabe.save()
            return redirect('aufgaben_liste')
    else:
        form = AufgabeForm()
    return render(request, 'posts/neue_aufgabe.html', {'form': form})

@login_required
def aufgaben_liste(request):
    aufgaben = Aufgabe.objects.all().order_by('id')
    return render(request, 'posts/aufgaben_liste.html', {'aufgaben': aufgaben})    