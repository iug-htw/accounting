from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import BaseUserManager
from posts.models import Unternehmen
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('Der Benutzername muss angegeben werden.')
        
        # Standardwerte für Felder, die nicht optional sind
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'teacher')  # Standardrolle für Superuser
        extra_fields.setdefault('semester', Semester.objects.first())  # Standardsemester
        extra_fields.setdefault('studiengang', Studiengang.objects.first())  # Standardstudiengang

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser muss is_staff=True haben.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser muss is_superuser=True haben.')

        return self.create_user(username, password, **extra_fields)


class Studiengang(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    ersteller = models.IntegerField(null=True, blank=True, verbose_name=_("Ersteller"))
    def __str__(self):
        return self.name

class Semester(models.Model):
    name = models.CharField(max_length=10, unique=True, verbose_name=_("Name"))
    ersteller = models.IntegerField(null=True, blank=True, verbose_name=_("Ersteller"))
    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    objects = CustomUserManager()
    ROLE_CHOICES = (
        ('student', _('Studierende')),
        ('teacher', _('Lehrkraft')),
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    # New field: each student has one professor, and professors can supervise many students
    professor = models.ForeignKey(
        'self',
        null=True, blank=True, 
        limit_choices_to={'role': 'teacher'},
        on_delete=models.SET_NULL,
        related_name='students', verbose_name=_("Professor")
    )
    semester = models.ForeignKey(Semester, null = True, on_delete=models.CASCADE, default = 1, verbose_name=_("Semester"))
    studiengang = models.ForeignKey(
        Studiengang,
        on_delete=models.CASCADE,
        null=True, blank=True,  # Allow empty reference initially
        related_name='students',  # Optional but recommended for clarity
        verbose_name=_("Studiengang")
    )
    unternehmen = models.ForeignKey(
        Unternehmen,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="studierende", verbose_name=_("Unternehmen")
    )
    display_name = models.CharField(max_length=150, blank=True, null=True, verbose_name=_("Anzeigename"))
    nutzergruppe = models.IntegerField(null=True, blank=True, verbose_name=_("Nutzergruppe"))  # Kann für Lehrer None sein
    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'
    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.username  # Standardwert setzen
        super().save(*args, **kwargs)