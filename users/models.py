from django.db import models
from django.contrib.auth.models import AbstractUser

class Studiengang(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Semester(models.Model):
    name = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Studierende'),
        ('teacher', 'Lehrkraft'),
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    # New field: each student has one professor, and professors can supervise many students
    professor = models.ForeignKey(
        'self',
        null=True, blank=True, 
        limit_choices_to={'role': 'teacher'},
        on_delete=models.SET_NULL,
        related_name='students'
    )
    semester = models.ForeignKey(Semester, null = True, on_delete=models.CASCADE, default = 1)
    studiengang = models.ForeignKey(
        Studiengang,
        on_delete=models.CASCADE,
        null=True, blank=True,  # Allow empty reference initially
        related_name='students'  # Optional but recommended for clarity
    )

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'