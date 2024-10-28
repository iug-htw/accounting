from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register_view, name="register"),
    path('login/', views.login_view, name="login"),
    path('logout/', views.logout_view, name="logout"),
    path('studiengang_hinzufuegen/', views.add_studiengang_view, name='add_studiengang'),
    path('delete_studiengang/<int:studiengang_id>/', views.delete_studiengang_view, name='delete_studiengang'),
]