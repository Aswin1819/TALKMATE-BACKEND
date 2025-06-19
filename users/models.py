from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import timedelta
import random,string
from django.utils import timezone

def generate_unique_id():
    while True:
        uid = "TM"+''.join(random.choices(string.digits,k=8))
        if not UserProfile.objects.filter(unique_id=uid).exists():
            return uid

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']


class Language(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=2)
    
    
class UserProfile(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active','Active'
        BANNED = 'banned','Banned'
        FLAGGED = 'flagged','Flagged'
    user = models.OneToOneField(CustomUser,on_delete=models.CASCADE)
    unique_id = models.CharField(max_length=10,unique=True,default=generate_unique_id)
    avatar = models.URLField(blank=True,null=True)
    bio = models.TextField(blank=True)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.ACTIVE)
    is_premium = models.BooleanField(default=False)
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    streak = models.IntegerField(default=0)
    total_speak_time = models.DurationField(default=timedelta)
    total_rooms_joined = models.IntegerField(default=0)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True,blank=True)
    following = models.ManyToManyField('self',symmetrical=False,related_name='followers',blank=True)
    
    def update_level(self):
        self.level = self.xp // 7200 + 1
        self.save()

class UserLanguage(models.Model):
    class Proficiency(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        ELEMENTARY = 'elementary', 'Elementary'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        NATIVE = 'native', 'Native'
        FLUENT = 'fluent', 'Fluent'

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    is_learning = models.BooleanField(default=True)
    proficiency = models.CharField(max_length=20, choices=Proficiency.choices)


    
class OTP(models.Model):
    user = models.ForeignKey(CustomUser,on_delete=models.CASCADE)
    code = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
class Friendship(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        BLOCKED = 'blocked', 'Blocked'

    from_user = models.ForeignKey(CustomUser, related_name='friendships_sent', on_delete=models.CASCADE)
    to_user = models.ForeignKey(CustomUser, related_name='friendships_received', on_delete=models.CASCADE)
    
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return f"{self.from_user} ➝ {self.to_user} ({self.status})"


    
class UserSettings(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    
    # UI toggles
    dark_mode = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    practice_reminders = models.BooleanField(default=True)
    room_interest_notifications = models.BooleanField(default=True)
    browser_notifications = models.BooleanField(default=True)
    
    # Visibility & activity settings
    public_profile = models.BooleanField(default=True)
    show_online_status = models.BooleanField(default=True)
    
    # Language & timezone
    language = models.ForeignKey('Language', on_delete=models.SET_NULL, null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s settings"
