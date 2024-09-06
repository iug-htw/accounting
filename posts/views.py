from django.shortcuts import render,redirect
from .models import Post
from django.contrib.auth.decorators import login_required
from . import forms

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

def buchungsaufgabe1(request):
    result = None

    if request.method == 'POST':
        number1 = int(request.POST.get('number1', 0))
        number2 = int(request.POST.get('number2', 0))
        result = number1 + number2

    return render(request, 'buchungsaufgabe.html', {'result': result})

def add_numbers(request):
    result = None
    if request.method == "POST":
        number1 = request.POST.get("number11")
        number2 = request.POST.get("number22")
        try:
            result1 = float(number1) + float(number2)
        except (ValueError, TypeError):
            result1 = "Ungültige Eingabe"
    
    return render(request, 'buchungsaufgabe.html', {'result': result1})