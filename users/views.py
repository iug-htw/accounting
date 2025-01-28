from django.shortcuts import render, redirect 
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm 
from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm, StudiengangForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.http import HttpResponse
from .models import Studiengang, Semester
from posts.views import lehrkraft_required

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
            print(form.cleaned_data)
            print(user.semester)
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