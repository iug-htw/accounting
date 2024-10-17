from django.shortcuts import render, redirect 
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm 
from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm
from django.contrib.auth import get_user_model

def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Verwende das benutzerdefinierte User-Modell
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')  
            return redirect("posts:list")
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
                return redirect("posts:list")
        return redirect("posts:list")
    else:
        form = AuthenticationForm()
    return render(request, "users/login.html", { "form": form })

def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("posts:list")