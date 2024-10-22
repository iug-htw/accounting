from django.db import models
from django.contrib.auth.models import AbstractUser

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

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'