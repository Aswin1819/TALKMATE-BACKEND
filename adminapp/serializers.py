from rest_framework import serializers
from users.models import CustomUser, UserProfile, UserLanguage, SubscriptionPlan,UserSubscription,Notification
from rooms.models import *
from rooms.serializers import TagSerializer, RoomParticipantSerializer
from django.utils import timezone
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils.timesince import timesince

class AdminLoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['is_superuser'] = user.is_superuser
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_superuser:
            raise serializers.ValidationError("You are not authorized as an admin.")
        
        data.update({
            'user_id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'is_superuser': self.user.is_superuser
        })
        return data

class UserListSerializer(serializers.ModelSerializer):
    is_premium = serializers.BooleanField(source='userprofile.is_premium', read_only=True)
    avatar = serializers.URLField(source='userprofile.avatar', read_only=True)
    level = serializers.IntegerField(source='userprofile.level', read_only=True)
    status = serializers.CharField(source='userprofile.status', read_only=True)
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'is_active', 'is_verified', 'date_joined',
                  'is_premium', 'avatar', 'level', 'status']

class UserProfileDetailSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    following_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'user_id', 'username', 'email', 'is_verified', 'date_joined',
            'unique_id', 'avatar', 'bio', 'status', 'is_premium', 'xp', 'level', 'streak',
            'total_speak_time', 'total_rooms_joined', 'is_online', 'last_seen',
            'following_count', 'followers_count', 'languages'
        ]

    def get_following_count(self, obj):
        return obj.following.count()

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_languages(self, obj):
        user_languages = UserLanguage.objects.filter(user_profile=obj)
        return [
            {
                'language': ul.language.name,
                'code': ul.language.code,
                'is_learning': ul.is_learning,
                'proficiency': ul.proficiency
            }
            for ul in user_languages
        ]

class RoomListSerializer(serializers.ModelSerializer):
    creator = serializers.CharField(source='host.username', read_only=True)
    type = serializers.CharField(source='room_type.name', read_only=True)
    language = serializers.CharField(source='language.name', read_only=True)
    activeUsers = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    
    class Meta:
        model = Room
        fields = [
            'id', 'title', 'creator', 'type', 'language',
            'activeUsers', 'status', 'createdAt'
        ]
        
    def get_activeUsers(self, obj):
        return obj.participants.filter(left_at__isnull=True).count()
    


class RoomDetailSerializer(serializers.ModelSerializer):
    creator = serializers.CharField(source='host.username', read_only=True)
    type = serializers.CharField(source='room_type.name', read_only=True)
    language = serializers.CharField(source='language.name', read_only=True)
    activeUsers = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    members = serializers.SerializerMethodField()
    description = serializers.CharField()

    class Meta:
        model = Room
        fields = [
            'id', 'title', 'creator', 'type', 'language',
            'activeUsers', 'status', 'createdAt', 'tags', 'members', 'description'
        ]

    def get_activeUsers(self, obj):
        return obj.participants.filter(left_at__isnull=True).count()
    
    def get_members(self, obj):
        
        seen = set()
        unique_participants = []
        for participant in obj.participants.order_by('-joined_at'):
            if participant.user.id not in seen:
                unique_participants.append(participant)
                seen.add(participant.user.id)
        return RoomParticipantSerializer(unique_participants, many=True).data
            
    
class AdminRoomEditSerializer(serializers.ModelSerializer):
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Room
        fields = [
            'title', 'description', 'room_type', 'language',
            'tag_ids', 'max_participants', 'is_private', 'status'
        ]

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        return instance


class AdminReportedRoomSerializer(serializers.ModelSerializer):
    reporter = serializers.CharField(source='reported_by.username', read_only=True)
    reporterAvatar = serializers.SerializerMethodField()
    reported = serializers.CharField(source='reported_user.username', read_only=True)
    reportedAvatar = serializers.SerializerMethodField()
    roomName = serializers.CharField(source='room.title', read_only=True)
    roomId = serializers.IntegerField(source='room.id', read_only=True)
    reporterId = serializers.IntegerField(source='reported_by.id', read_only=True)
    reportedId = serializers.IntegerField(source='reported_user.id', read_only=True)
    reasonLabel = serializers.SerializerMethodField()

    class Meta:
        model = ReportedRoom
        fields = [
            'id', 'reason','reasonLabel', 'reporter','reporterAvatar', 'reported','reportedAvatar', 'roomName', 'roomId',
            'reporterId', 'reportedId', 'timestamp', 'status'
        ]

    def get_reporterAvatar(self, obj):
        if obj.reported_by and hasattr(obj.reported_by, 'userprofile'):
            return obj.reported_by.userprofile.avatar
        return None

    def get_reportedAvatar(self, obj):
        if obj.reported_user and hasattr(obj.reported_user, 'userprofile'):
            return obj.reported_user.userprofile.avatar
        return None

    def get_reasonLabel(self, obj):
        return obj.get_reason_display()

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
        

class UserSubscriptionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    plan = serializers.CharField(source='plan.name', read_only=True)
    planId = serializers.CharField(source='plan.id', read_only=True)
    amount = serializers.SerializerMethodField()
    paymentMethod = serializers.CharField(source='payment_status', read_only=True)
    status = serializers.SerializerMethodField()
    startDate = serializers.DateTimeField(source='start_date', read_only=True)
    endDate = serializers.DateTimeField(source='end_date', read_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'username', 'email', 'plan', 'planId', 'startDate', 'endDate',
            'status', 'amount', 'paymentMethod'
        ]

    def get_amount(self, obj):
        return f"₹{obj.plan.price}" if obj.plan and obj.plan.price else ""

    def get_status(self, obj):
        if not obj.is_active:
            return "canceled"
        if obj.end_date and obj.end_date < timezone.now():
            return "expired"
        return "active"

class AdminNotificationSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()
    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'message', 'is_read', 'created_at', 'link', 'time']

    def get_time(self, obj):
        return timesince(obj.created_at) + ' ago'