from django.db import models

from django.contrib.auth.models import AbstractUser, PermissionsMixin

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Studierende'),
        ('teacher', 'Lehrkraft'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')

    # Add related_name to groups to avoid clash
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        related_name='customuser_groups'  # Change related_name to avoid conflict
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        related_name='customuser_set'  # Already adjusted previously
    )
