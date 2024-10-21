from django.shortcuts import render
#from django.core.exceptions import PermissionDenied


# Create your views here.
def vorlage(request):
    return render(request, 'vorlage.html')
#def buchungsaufgabe(request):
#    return render(request, 'buchungsaufgabe.html')
def index(request):
    return render(request, 'index.html')
def themenkomplex1(request):
    return render(request, 'themenkomplex1.html')
def themenkomplex2(request):
    return render(request, 'themenkomplex2.html')
def themenkomplex3(request):
    return render(request, 'themenkomplex3.html')

#def custom_permission_denied_view(request, exception):
#    return render(request, 'errors/permission_denied.html', status=403)
