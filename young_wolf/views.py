from django.shortcuts import render
from django.contrib.auth.decorators import login_required
#from django.core.exceptions import PermissionDenied


# Create your views here.
def vorlage(request):
    return render(request, 'vorlage.html')
#def buchungsaufgabe(request):
#    return render(request, 'buchungsaufgabe.html')
@login_required(login_url="/users/login/")
def index(request):
    # Wenn der eingeloggte Nutzer eine Lehrkraft ist, hole die zugeordneten Studierenden
    students = request.user.students.all() if request.user.role == 'teacher' else None
    return render(request, 'index.html', {'students': students})
def themenkomplex1(request):
    return render(request, 'themenkomplex1.html')
def themenkomplex2(request):
    return render(request, 'themenkomplex2.html')
def themenkomplex3(request):
    return render(request, 'themenkomplex3.html')

#def custom_permission_denied_view(request, exception):
#    return render(request, 'errors/permission_denied.html', status=403)
