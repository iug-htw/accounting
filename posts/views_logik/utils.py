from .bibliotheken import *
from .bibliotheken import _

#Hier werden grundlegende Hilfsfunktion abgelegt. Das beinhaltet u.a. die Decorators (Berechtigungen) oder Parser von texten

# Für Lehrkräfte
def lehrkraft_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.role == 'teacher' or request.user.is_superuser):
            return view_func(request, *args, **kwargs)
        else:
           return fehlende_berechtigung_response()
    return _wrapped_view_func

# Für Studierende
def student_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'student':
            return fehlende_berechtigung_response()
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

#Für Admins
def admin_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            return fehlende_berechtigung_response()
    return _wrapped_view_func

def fehlende_berechtigung_response():
    return HttpResponse(
        _('Fehlende Berechtigung<br><a href="%(link)s">Zurück zur Startseite</a>') % {
            "link": reverse("index")
        }
    )

#JSON Parsing
def safe_parse(val):
    if isinstance(val, str):
        return json.loads(val or "[]")
    return val or []
