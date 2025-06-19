from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserProfile,UserSettings

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile_settings(sender, instance, created, **kwargs):
    """
    Create a UserProfile and UserSettings instance whenever a new user is created.
    """
    if created:
        UserProfile.objects.create(user=instance)
        print(f"Created UserProfile for user: {instance.username}")
        UserSettings.objects.create(user=instance)
        print(f"Created UserSettings for user: {instance.username}")