from rest_framework import serializers
from .models import Room, RoomParticipant, Message, Tag, RoomType,ReportedRoom
from users.models import Language

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color']

class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = ['id', 'name', 'description']

class RoomParticipantSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = RoomParticipant
        fields = ['user_id', 'username', 'role', 'joined_at', 'is_muted', 'hand_raised','avatar']
        
    def get_avatar(self, obj):
        try:
            return obj.user.userprofile.avatar
        except:
            return None
        

class RoomSerializer(serializers.ModelSerializer):
    host_username = serializers.CharField(source='host.username', read_only=True)
    participant_count = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)
    room_type_name = serializers.CharField(source='room_type.name', read_only=True)
    language_name = serializers.CharField(source='language.name', read_only=True)
    
    class Meta:
        model = Room
        fields = [
            'id', 'title', 'description', 'host', 'host_username',
            'room_type', 'room_type_name', 'language', 'language_name',
            'tags', 'max_participants', 'participant_count', 'is_private',
            'status', 'created_at', 'started_at'
        ]
        read_only_fields = ['host', 'created_at', 'started_at']
    
    def get_participant_count(self, obj):
        return obj.participants.filter(left_at__isnull=True).count()

class CreateRoomSerializer(serializers.ModelSerializer):
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Room
        fields = [
            'title', 'description', 'room_type', 'language',
            'tag_ids', 'max_participants', 'is_private', 'password'
        ]
    
    def validate_max_participants(self, value):
        if value < 2 or value > 10:
            raise serializers.ValidationError("Max participants must be between 2 and 10")
        return value
    
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        password = validated_data.pop('password',None)
        room = Room.objects.create(**validated_data)
        
        if password:
            room.set_password(password)
            room.save()

        if tag_ids:
            room.tags.set(tag_ids)
        
        return room

class MessageSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = ['id', 'user', 'username', 'content', 'message_type', 'sent_at','avatar']
        read_only_fields = ['user', 'sent_at']
    
    def get_avatar(self, obj):
        try:
            return obj.user.userprofile.avatar
        except:
            return None


class ReportedRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportedRoom
        fields = ['id', 'room', 'reported_by', 'reported_user', 'reason', 'timestamp', 'status']
        read_only_fields = ['id', 'timestamp', 'status', 'reported_by','room', 'reported_user']