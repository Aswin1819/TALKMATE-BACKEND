from django.db.models.signals import post_save,post_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.cache import cache
from .models import UserProfile,UserSettings

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile_settings(sender, instance, created, **kwargs):
    """
    Create a UserProfile and UserSettings instance whenever a new user is created.
    """
    if created:
        UserProfile.objects.create(user=instance)
        UserSettings.objects.create(user=instance)

@receiver([post_save,post_delete],sender=UserProfile)
def invalidate_userprofile_cache(sender, instance, **kwargs):
    """
    Deleting the Cache for requested user 
    """
    cache_key = f"user_profile_{instance.user.id}"
    cache.delete(cache_key)


