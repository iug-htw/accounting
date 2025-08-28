from django.shortcuts import render
from django.contrib.auth.decorators import login_required
#from django.core.exceptions import PermissionDenied
from django.utils import translation
from django.conf import settings
from django.shortcuts import redirect
from collections import defaultdict
from operator import attrgetter
from posts.models import NutzerAbschluss

@login_required(login_url="/users/login/")
def index(request):
    grouped_students = {}

    if request.user.role == 'teacher':
        students = request.user.students.all().select_related('semester', 'studiengang')

        grouped_students = defaultdict(lambda: defaultdict(list))

        for student in students:
            semester_name = student.semester.name if student.semester else "Unbekanntes Semester"
            studiengang_name = student.studiengang.name if student.studiengang else "Unbekannter Studiengang"

            # GuV/Bilanz Status abrufen
            abschluss_info = {}
            for typ in ["GUV", "BILANZ"]:
                abschluss = NutzerAbschluss.objects.filter(nutzer=student, typ=typ).first()
                if abschluss is None or abschluss.korrekt is None:
                    abschluss_info[typ] = None   # nicht bearbeitet
                elif abschluss.korrekt:
                    abschluss_info[typ] = 1      # korrekt
                else:
                    abschluss_info[typ] = 0      # falsch

            # Student + Info speichern
            grouped_students[semester_name][studiengang_name].append({
                "student": student,
                "abschluss": abschluss_info
            })

        grouped_students = dict(sorted(grouped_students.items()))
        for semester in grouped_students:
            grouped_students[semester] = dict(sorted(grouped_students[semester].items()))

    return render(request, 'index.html', {'grouped_students': grouped_students})
def frontpage(request):
    return render(request, 'frontpage.html')
