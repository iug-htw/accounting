from django.shortcuts import render
from django.contrib.auth.decorators import login_required
#from django.core.exceptions import PermissionDenied
from django.utils import translation
from django.conf import settings
from django.shortcuts import redirect
from collections import defaultdict
from operator import attrgetter

@login_required(login_url="/users/login/")
def index(request):
    grouped_students = {}

    if request.user.role == 'teacher':
        students = request.user.students.all().select_related('semester', 'studiengang')

        # Gruppierung: {semester_name: {studiengang_name: [students]}}
        grouped_students = defaultdict(lambda: defaultdict(list))

        for student in students:
            semester_name = student.semester.name if student.semester else "Unbekanntes Semester"
            studiengang_name = student.studiengang.name if student.studiengang else "Unbekannter Studiengang"
            grouped_students[semester_name][studiengang_name].append(student)

        # Optional sortieren
        grouped_students = dict(sorted(grouped_students.items()))  # Semester sortieren
        for semester in grouped_students:
            grouped_students[semester] = dict(sorted(grouped_students[semester].items()))  # Studiengänge sortieren

    return render(request, 'index.html', {'grouped_students': grouped_students})
def frontpage(request):
    return render(request, 'frontpage.html')
