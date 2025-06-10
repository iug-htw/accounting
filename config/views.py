from django.shortcuts import render
from django.contrib.auth.decorators import login_required
#from django.core.exceptions import PermissionDenied
from django.utils import translation
from django.shortcuts import redirect

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
def frontpage2(request):
    return render(request, 'frontpage2.html')
def frontpage(request):
    return render(request, 'frontpage.html')

#def custom_permission_denied_view(request, exception):
#    return render(request, 'errors/permission_denied.html', status=403)
def set_language(request):
    if request.method == "POST":
        lang = request.POST.get('language')
        if lang in ['de', 'en']:
            request.session[translation.LANGUAGE_SESSION_KEY] = lang
            translation.activate(lang)
    return redirect(request.META.get('HTTP_REFERER', '/'))