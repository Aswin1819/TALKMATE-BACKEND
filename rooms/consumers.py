import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from django.contrib.auth.models import AnonymousUser
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
        #Multiple join prevention
        # already_joined = await self.user_has_active_room()
        # print("already_joined:",already_joined)
        # if already_joined:
        #     await self.close()
        #     return 
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
        # Request audio connections with existing participants
        await self.request_audio_connections()
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            
            #handle if the user is host
            await self.handle_host_disconnect()
            
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
            elif message_type == 'toggle_video':
                await self.handle_toggle_video(data)
            elif message_type == 'raise_hand':
                await self.handle_raise_hand(data)
            elif message_type == 'request_audio_connection':
                await self.handle_request_audio_connection(data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': 'Server error'
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
        
        if not target_user or not offer:
            return
            
        # Send only to specific user using their channel
        await self.send_to_user(target_user, {
            'type': 'webrtc_offer',
            'from_user_id': self.user.id,
            'target_user_id': target_user,
            'offer': offer
        })

    async def handle_webrtc_answer(self, data):
        target_user = data.get('target_user_id')
        answer = data.get('answer')
        
        if not target_user or not answer:
            return
            
        # Send only to specific user
        await self.send_to_user(target_user, {
            'type': 'webrtc_answer',
            'from_user_id': self.user.id,
            'target_user_id': target_user,
            'answer': answer
        })

    async def handle_ice_candidate(self, data):
        target_user = data.get('target_user_id')
        candidate = data.get('candidate')
        
        if not target_user or not candidate:
            return
            
        # Send only to specific user
        await self.send_to_user(target_user, {
            'type': 'ice_candidate',
            'from_user_id': self.user.id,
            'target_user_id': target_user,
            'candidate': candidate
        })

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

    async def handle_toggle_video(self, data):
        video_enabled = data.get('video_enabled', False)
        await self.update_participant_video_status(video_enabled)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_video_toggle',
                'user_id': self.user.id,
                'video_enabled': video_enabled
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

    async def handle_request_audio_connection(self, data):
        # Get all participants except the requester
        participants = await self.get_room_participants()
        
        for participant in participants:
            if participant['user_id'] != self.user.id:
                await self.send_to_user(participant['user_id'], {
                    'type': 'audio_connection_request',
                    'from_user_id': self.user.id,
                    'username': self.user.username
                })

    # Helper method to send message to specific user
    async def send_to_user(self, user_id, message):
        # This is a simplified approach - in production, you might want to track user channels
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                **message,
                '_target_user_id': user_id  # Internal flag
            }
        )

    async def request_audio_connections(self):
        """Send audio connection requests to existing participants"""
        participants = await self.get_room_participants()
        
        for participant in participants:
            if participant['user_id'] != self.user.id:
                await self.send_to_user(participant['user_id'], {
                    'type': 'audio_connection_request',
                    'from_user_id': self.user.id,
                    'username': self.user.username
                })

    # WebSocket Event Handlers (called by group_send)
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username'],
            'message': event['message'],
            'timestamp': event['timestamp']
        }))

    async def user_joined(self, event):
        await self.send(text_data=json.dumps(event))

    async def user_left(self, event):
        await self.send(text_data=json.dumps(event))

    async def webrtc_offer(self, event):
        # Only send to target user
        target_user_id = event.get('_target_user_id', event.get('target_user_id'))
        if target_user_id == self.user.id:
            await self.send(text_data=json.dumps({
                'type': event['type'],
                'from_user_id': event['from_user_id'],
                'target_user_id': event['target_user_id'],
                'offer': event['offer']
            }))

    async def webrtc_answer(self, event):
        # Only send to target user
        target_user_id = event.get('_target_user_id', event.get('target_user_id'))
        if target_user_id == self.user.id:
            await self.send(text_data=json.dumps({
                'type': event['type'],
                'from_user_id': event['from_user_id'],
                'target_user_id': event['target_user_id'],
                'answer': event['answer']
            }))

    async def ice_candidate(self, event):
        # Only send to target user
        target_user_id = event.get('_target_user_id', event.get('target_user_id'))
        if target_user_id == self.user.id:
            await self.send(text_data=json.dumps({
                'type': event['type'],
                'from_user_id': event['from_user_id'],
                'target_user_id': event['target_user_id'],
                'candidate': event['candidate']
            }))

    async def user_mute_toggle(self, event):
        await self.send(text_data=json.dumps(event))

    async def user_video_toggle(self, event):
        await self.send(text_data=json.dumps(event))

    async def hand_raised(self, event):
        await self.send(text_data=json.dumps(event))

    async def audio_connection_request(self, event):
        # Only send to target user
        target_user_id = event.get('_target_user_id')
        if target_user_id == self.user.id:
            await self.send(text_data=json.dumps({
                'type': event['type'],
                'from_user_id': event['from_user_id'],
                'username': event['username']
            }))

    # Database Operations
    @database_sync_to_async
    def check_room_access(self):
        from .models import Room, RoomParticipant
        try:
            room = Room.objects.get(id=self.room_id, status='live')
            
            # Check if room is private and needs password
            if room.is_private:
                #  handle password validation here
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
        from django.utils import timezone

        room = Room.objects.get(id=self.room_id)

        # Try to find an existing (inactive) participant
        participant = RoomParticipant.objects.filter(
            user=self.user,
            room=room
        ).order_by('-joined_at').first()

        if participant:
            # If participant had left earlier, rejoin
            if participant.left_at is not None:
                participant.left_at = None
                participant.joined_at = timezone.now()
                participant.is_muted = False
                participant.hand_raised = False
                participant.video_enabled = False
                participant.save()
        else:
            # Create new participant record
            participant = RoomParticipant.objects.create(
                user=self.user,
                room=room,
                role='participant',
                is_muted=False,
                hand_raised=False,
                video_enabled=False
            )

        # If this user is the host of the room, assign role
        if room.host == self.user and participant.role != 'host':
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
            self.calculate_stats_on_leave(participant)
        except RoomParticipant.DoesNotExist:
            pass

    @database_sync_to_async
    def save_message(self, content):
        from .models import Room, Message
        
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
        from .models import RoomParticipant
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
    def update_participant_video_status(self, video_enabled):
        from .models import RoomParticipant
        try:
            participant = RoomParticipant.objects.get(
                user=self.user,
                room_id=self.room_id,
                left_at__isnull=True
            )
            participant.video_enabled = video_enabled
            participant.save()
        except RoomParticipant.DoesNotExist:
            pass

    @database_sync_to_async
    def update_participant_hand_status(self, hand_raised):
        from .models import RoomParticipant
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
                'video_enabled': p.video_enabled,   #getattr(p, 'video_enabled', False)
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
        

    # @database_sync_to_async
    # def user_has_active_room(self):
    #     from .models import RoomParticipant
    #     is_room_participant=RoomParticipant.objects.filter(
    #         user=self.user,
    #         room_id=self.room_id,
    #         left_at__isnull=True
    #     ).exists()
    #     print("is_room_participant:",is_room_participant)
    #     return is_room_participant
    

    @database_sync_to_async
    def handle_host_disconnect(self):
        from .models import Room,RoomParticipant
        room = Room.objects.get(id=self.room_id)
        if room.host == self.user:
            # Finding another participant to become host
            next_participant = RoomParticipant.objects.filter(
                room=room, 
                left_at__isnull=True
            ).exclude(user=self.user).first()
            
            if next_participant:
                room.host = next_participant.user
                room.save()
                next_participant.role = 'host'
                next_participant.save()
            else:
                # No participants left, end room
                room.status = 'ended'
                room.ended_at = timezone.now()
                room.save()
            

    @database_sync_to_async
    def calculate_stats_on_leave(self, participant):
        from .models import UserActivity
        from datetime import timedelta

        now = timezone.now()
        participant.left_at = now
        participant.save()

        duration = (participant.left_at - participant.joined_at).total_seconds()
        minutes = max(1, int(duration // 60))

        profile = participant.user.userprofile
        profile.total_speak_time = (profile.total_speak_time or timedelta()) + timedelta(minutes=minutes)
        profile.xp += minutes * 20
        profile.level = profile.xp // 1000 + 1
        profile.save()

        activity, _ = UserActivity.objects.get_or_create(user=participant.user, date=now.date())
        activity.xp_earned += minutes * 20
        activity.practice_minutes += minutes
        activity.save()
