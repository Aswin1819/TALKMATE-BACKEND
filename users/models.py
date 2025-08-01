from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import timedelta
import random,string
from django.utils import timezone
from django.db.models import Count

def generate_unique_id():
    while True:
        uid = "TM"+''.join(random.choices(string.digits,k=8))
        if not UserProfile.objects.filter(unique_id=uid).exists():
            return uid

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    is_google_login = models.BooleanField(default=False, db_index=True)
    
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
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.ACTIVE, db_index=True)
    is_premium = models.BooleanField(default=False, db_index=True)
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    streak = models.IntegerField(default=0)
    total_speak_time = models.DurationField(default=timedelta)
    total_rooms_joined = models.IntegerField(default=0)
    is_online = models.BooleanField(default=False, db_index=True)
    last_seen = models.DateTimeField(null=True,blank=True)
    following = models.ManyToManyField('self',symmetrical=False,related_name='followers',blank=True)
    
    def update_level(self):
        self.level = self.xp // 7200 + 1
        self.save()

    def follow_user(self,user_profile):
        self.following.add(user_profile)

    def unfollow_user(self, user_profile):
        self.following.remove(user_profile)

    def is_following(self, user_profile):
        return self.following.filter(id=user_profile.id).exists()

    def is_followed_by(self,user_profile):
        return self.followers.filter(id=user_profile.id).exists()

    def mutual_friends_qs(self):
        return self.following.filter(following=self).distinct()
    
    def friends_count(self):
        return self.mutual_friends_qs().count()

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
    code = models.CharField(max_length=50, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used = models.BooleanField(default=False, db_index=True)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
class Friendship(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        BLOCKED = 'blocked', 'Blocked'

    from_user = models.ForeignKey(CustomUser, related_name='friendships_sent', on_delete=models.CASCADE)
    to_user = models.ForeignKey(CustomUser, related_name='friendships_received', on_delete=models.CASCADE)
    
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
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
    
    
class Notification(models.Model):
    class NotificationType(models.TextChoices):
        REPORT = 'report', 'New Report'
        USER_REGISTRATION = 'user_registration', 'New User Registration'
        SYSTEM_UPDATE = 'system_update', 'System Update'
        FRIEND_REQUEST = 'friend_request', 'Friend Request'
        ROOM_INVITE = 'room_invite', 'Room Invite'
        NEW_FOLLOWER = 'new_follower', 'New Follower'
        CHAT_MESSAGE = 'chat_message', 'New Chat Message'
        OTHER = 'other', 'Other'

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='User to whom this notification is shown'
    )
    type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.OTHER,
        db_index=True
    )
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.URLField(blank=True, null=True, help_text='Optional link to redirect on click')
    related_user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='sent_notifications',
        help_text='User who triggered this notification'
    )
    related_room = models.ForeignKey(
        'rooms.Room',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Related room for room-specific notifications'
    )

    def __str__(self):
        return f"{self.user.username} - {self.title}"

    class Meta:
        ordering = ['-created_at']


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100,unique=True)
    price = models.DecimalField(max_digits=10,decimal_places=2)
    duration_days = models.IntegerField()
    features = models.TextField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    
class UserSubscription(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True, db_index=True)

    payment_id = models.CharField(max_length=255, blank=True, null=True)  
    payment_status = models.CharField(max_length=50, default='pending', db_index=True) 

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
    
class UserSubscriptionHistory(models.Model):
    user = models.ForeignKey(CustomUser,on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan,on_delete=models.SET_NULL,null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    payment_id = models.CharField(max_length=255,blank=True,null=True)
    payment_status = models.CharField(max_length=50,default='paid', db_index=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name} (History)"


class ChatRoom(models.Model):
    participants = models.ManyToManyField(CustomUser, related_name='chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        participant_names = [p.username for p in self.participants.all()]
        return f"Chat between {', '.join(participant_names)}"
    
    @classmethod
    def get_or_create_room(cls, user1, user2):
        existing_room = cls.objects.filter(
            participants=user1
        ).filter(
            participants=user2
        ).annotate(
            participant_count=Count('participants')
        ).filter(
            participant_count=2
        ).first()
        
        if existing_room:
            return existing_room
        
        room = cls.objects.create()
        room.participants.add(user1, user2)
        return room

class ChatMessage(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('emoji', 'Emoji')
    ]
    
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        ordering = ['sent_at']
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"


    
    

        
