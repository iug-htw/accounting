from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register_view, name="register"),
    path('login/', views.login_view, name="login"),
    path('logout/', views.logout_view, name="logout"),
    path('studiengang_hinzufuegen/', views.add_studiengang_view, name='add_studiengang'),
    path('delete_studiengang/<int:studiengang_id>/', views.delete_studiengang_view, name='delete_studiengang'),
    path('bulk_student_creation/', views.bulk_student_creation, name='bulk_student_creation'),
    path('add_semester/', views.add_semester_view, name='add_semester'),
    path('delete_semester/<int:semester_id>/', views.delete_semester_view, name='delete_semester'),

]