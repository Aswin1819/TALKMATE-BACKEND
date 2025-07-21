from rest_framework import serializers
from .models import Room, RoomParticipant, Message, Tag, RoomType,ReportedRoom
from users.models import Language

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color']

    def validate_name(self, value):
        if self.instance:
            if Tag.objects.filter(name__iexact=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("Tag with this name already exists")
        else:
            if Tag.objects.filter(name__iexact=value).exists():
                raise serializers.ValidationError("Tag with this name already exists")
        return value

class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = ['id', 'name', 'description']
    
    def validate_name(self, value):
        if self.instance:
            if RoomType.objects.filter(name__iexact=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("RoomType with this name already exists")
        else:
            if RoomType.objects.filter(name__iexact=value).exists():
                raise serializers.ValidationError("RoomType with this name already exists")
        return value

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
    host_avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = Room
        fields = [
            'id', 'title', 'description', 'host', 'host_username','host_avatar',
            'room_type', 'room_type_name', 'language', 'language_name',
            'tags', 'max_participants', 'participant_count', 'is_private',
            'status', 'created_at', 'started_at',
        ]
        read_only_fields = ['host', 'created_at', 'started_at']
    
    def get_participant_count(self, obj):
        return obj.participants.filter(left_at__isnull=True).count()
    
    def get_host_avatar(self, obj):
        try:
            return obj.host.userprofile.avatar
        except:
            return None

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

class EditRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = [
            'title', 'description', 'is_private', 'room_type', 'language',
            'tags', 'max_participants', 'password'
        ]

    def validate(self, data):
        user = self.context['request'].user
        if data.get('is_private') and not user.userprofile.is_premium:
            raise serializers.ValidationError("Only premium users can create rooms")
        return data

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)  # Hash and set the password
        instance.save()
        return instance

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
    reason = serializers.ChoiceField(choices=ReportedRoom.REASON_CHOICES)
    custom_description = serializers.CharField(
        max_length=500, 
        required=False, 
        allow_blank=True,
        allow_null=True  # Allow null values
    )

    class Meta:
        model = ReportedRoom
        fields = ['reason', 'custom_description']

    def validate(self, data):
        if data.get('reason') == 'other' and not data.get('custom_description'):
            raise serializers.ValidationError(
                "Custom description is required when 'other' reason is selected"
            )
        return data