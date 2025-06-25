import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from django.contrib.auth.models import AnonymousUser
        from .models import Room, RoomParticipant, Message
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_id}'
        self.user = self.scope['user']
        
        # Check if user is authenticated
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return
        
        # Check if room exists and user can join
        room_access = await self.check_room_access()
        if not room_access:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Add user as participant
        await self.add_participant()
        
        # Notify others about new participant
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': self.user.id,
                'username': self.user.username,
                'message': f'{self.user.username} joined the room'
            }
        )
        
        # Send current room state to new user
        await self.send_room_state()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Remove user from participants
            await self.remove_participant()
            
            # Notify others about user leaving
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'message': f'{self.user.username} left the room'
                }
            )
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'webrtc_offer':
                await self.handle_webrtc_offer(data)
            elif message_type == 'webrtc_answer':
                await self.handle_webrtc_answer(data)
            elif message_type == 'webrtc_ice_candidate':
                await self.handle_ice_candidate(data)
            elif message_type == 'toggle_mute':
                await self.handle_toggle_mute(data)
            elif message_type == 'raise_hand':
                await self.handle_raise_hand(data)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
    
    # Message Handlers
    async def handle_chat_message(self, data):
        message_content = data.get('message', '').strip()
        if not message_content:
            return
        
        # Save message to database
        message = await self.save_message(message_content)
        
        # Broadcast to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': message.id,
                'user_id': self.user.id,
                'username': self.user.username,
                'message': message_content,
                'timestamp': message.sent_at.isoformat()
            }
        )
    
    async def handle_webrtc_offer(self, data):
        target_user = data.get('target_user_id')
        offer = data.get('offer')
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_offer',
                'from_user_id': self.user.id,
                'target_user_id': target_user,
                'offer': offer
            }
        )
    
    async def handle_webrtc_answer(self, data):
        target_user = data.get('target_user_id')
        answer = data.get('answer')
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_answer',
                'from_user_id': self.user.id,
                'target_user_id': target_user,
                'answer': answer
            }
        )
    
    async def handle_ice_candidate(self, data):
        target_user = data.get('target_user_id')
        candidate = data.get('candidate')
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'ice_candidate',
                'from_user_id': self.user.id,
                'target_user_id': target_user,
                'candidate': candidate
            }
        )
    
    async def handle_toggle_mute(self, data):
        is_muted = data.get('is_muted', False)
        await self.update_participant_mute_status(is_muted)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_mute_toggle',
                'user_id': self.user.id,
                'is_muted': is_muted
            }
        )
    
    async def handle_raise_hand(self, data):
        hand_raised = data.get('hand_raised', False)
        await self.update_participant_hand_status(hand_raised)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'hand_raised',
                'user_id': self.user.id,
                'hand_raised': hand_raised
            }
        )
    
    # WebSocket Event Handlers (called by group_send)
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def user_joined(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def user_left(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def webrtc_offer(self, event):
        # Only send to target user
        if event['target_user_id'] == self.user.id:
            await self.send(text_data=json.dumps(event))
    
    async def webrtc_answer(self, event):
        # Only send to target user
        if event['target_user_id'] == self.user.id:
            await self.send(text_data=json.dumps(event))
    
    async def ice_candidate(self, event):
        # Only send to target user
        if event['target_user_id'] == self.user.id:
            await self.send(text_data=json.dumps(event))
    
    async def user_mute_toggle(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def hand_raised(self, event):
        await self.send(text_data=json.dumps(event))
    
    # Database Operations
    @database_sync_to_async
    def check_room_access(self):
        from .models import Room, RoomParticipant

        try:
            room = Room.objects.get(id=self.room_id, status='live')
            
            # Check if room is private and needs password
            if room.is_private:
                # You'll need to handle password validation here
                # For now, assume public rooms only
                pass
            
            # Check max participants
            current_participants = RoomParticipant.objects.filter(
                room=room, 
                left_at__isnull=True
            ).count()
            
            if current_participants >= room.max_participants:
                return False
            
            return True
            
        except Room.DoesNotExist:
            return False
    
    @database_sync_to_async
    def add_participant(self):
        from .models import Room, RoomParticipant
        room = Room.objects.get(id=self.room_id)
        participant, created = RoomParticipant.objects.get_or_create(
            user=self.user,
            room=room,
            left_at__isnull=True,
            defaults={'role': 'participant'}
        )
        
        # If user is the host, update role
        if room.host == self.user:
            participant.role = 'host'
            participant.save()
        
        return participant
    
    @database_sync_to_async
    def remove_participant(self):
        from .models import Room, RoomParticipant
        try:
            participant = RoomParticipant.objects.get(
                user=self.user,
                room_id=self.room_id,
                left_at__isnull=True
            )
            participant.left_at = timezone.now()
            participant.save()
        except RoomParticipant.DoesNotExist:
            pass
    
    @database_sync_to_async
    def save_message(self, content):
        from .models import Room, RoomParticipant,Message
        room = Room.objects.get(id=self.room_id)
        message = Message.objects.create(
            room=room,
            user=self.user,
            content=content,
            message_type='text'
        )
        return message
    
    @database_sync_to_async
    def update_participant_mute_status(self, is_muted):
        from .models import Room, RoomParticipant
        try:
            participant = RoomParticipant.objects.get(
                user=self.user,
                room_id=self.room_id,
                left_at__isnull=True
            )
            participant.is_muted = is_muted
            participant.save()
        except RoomParticipant.DoesNotExist:
            pass
    
    @database_sync_to_async
    def update_participant_hand_status(self, hand_raised):
        from .models import Room, RoomParticipant
        try:
            participant = RoomParticipant.objects.get(
                user=self.user,
                room_id=self.room_id,
                left_at__isnull=True
            )
            participant.hand_raised = hand_raised
            participant.save()
        except RoomParticipant.DoesNotExist:
            pass
    
    @database_sync_to_async
    def get_room_participants(self):
        from .models import Room, RoomParticipant
        room = Room.objects.get(id=self.room_id)
        participants = RoomParticipant.objects.filter(
            room=room,
            left_at__isnull=True
        ).select_related('user')
        
        return [
            {
                'user_id': p.user.id,
                'username': p.user.username,
                'role': p.role,
                'is_muted': p.is_muted,
                'hand_raised': p.hand_raised,
                'joined_at': p.joined_at.isoformat()
            }
            for p in participants
        ]
    
    async def send_room_state(self):
        participants = await self.get_room_participants()
        
        await self.send(text_data=json.dumps({
            'type': 'room_state',
            'participants': participants,
            'room_id': self.room_id
        }))