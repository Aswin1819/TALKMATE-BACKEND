from django.db import models
from django.contrib.auth import get_user_model
from users.models import Language
import uuid

User = get_user_model()

# Create your models here.
class Tag(models.Model):
    name = models.CharField(max_length=30)
    color = models.CharField(max_length=7, default='#ffffff')

class RoomType(models.Model):
    name = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    
class Room(models.Model):
    STATUS_CHOICES = [
        ('live', 'Live'),
        ('ended', 'Ended'),
        ('scheduled', 'Scheduled')
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    host = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='hosted_rooms')
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    room_type = models.ForeignKey(RoomType, on_delete=models.SET_NULL, null=True)
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True)
    tags = models.ManyToManyField(Tag, blank=True)

    max_participants = models.IntegerField(default=6)
    is_private = models.BooleanField(default=False)
    password = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='live')
    is_deleted = models.BooleanField(default=False)

class RoomParticipant(models.Model):
    class Role(models.TextChoices):
        HOST = 'host', 'Host'
        COHOST = 'cohost', 'Co-host'
        PARTICIPANT = 'participant', 'Participant'

    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='participants')
    role = models.CharField(max_length=20, choices=Role.choices, default='participant')

    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    is_muted = models.BooleanField(default=False)
    hand_raised = models.BooleanField(default=False)
    video_enabled = models.BooleanField(default=False)

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('emoji', 'Emoji'),
        ('system', 'System')
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    sent_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    
    
class ReportedRoom(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    reported_by = models.ForeignKey(User, related_name='reports_made', on_delete=models.SET_NULL, null=True)
    reported_user = models.ForeignKey(User, related_name='reports_received', on_delete=models.SET_NULL, null=True)
    reason = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Report on {self.reported_user} by {self.reported_by} in {self.room}"
