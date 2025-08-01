import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from django.contrib.auth.models import AnonymousUser
        # Check if user is authenticated
        if isinstance(self.scope['user'], AnonymousUser):
            await self.close()
            return
            
        self.user = self.scope['user']
        self.user_group_name = f"user_{self.user.id}"

        # Join user's personal group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()

        # Update online status
        await self.update_online_status(True)
        logger.info(f"Chat WebSocket connected for user {self.user.username}")
    
    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.update_online_status(False)
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        logger.info(f"Chat WebSocket disconnected for user {getattr(self, 'user', 'unknown')}")
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'read_receipt':
                await self.handle_read_receipt(data)
            elif message_type == 'get_chat_history':
                await self.handle_get_chat_history(data)
            elif message_type == 'get_friends_list':
                await self.handle_get_friends_list(data)
            else:
                logger.warning(f"Unknown chat message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error handling chat message: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': 'Server error'
            }))
    
    async def handle_chat_message(self, data):
        recipient_id = data.get('recipient_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        
        if not content or not recipient_id:
            await self.send(text_data=json.dumps({
                'error': 'Missing required fields'
            }))
            return
        
        # Save message to database
        message = await self.save_chat_message(recipient_id, content, message_type)
        
        if message:
            # Send to recipient
            await self.channel_layer.group_send(
                f"user_{recipient_id}",
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': self.user.id,
                    'sender_username': self.user.username
                }
            )
            
            # Send confirmation to sender
            await self.send(text_data=json.dumps({
                'type': 'message_sent',
                'message_id': message['id'],
                'timestamp': message['sent_at']
            }))
    
    async def handle_typing(self, data):
        recipient_id = data.get('recipient_id')
        is_typing = data.get('is_typing', False)
        
        if recipient_id:
            await self.channel_layer.group_send(
                f"user_{recipient_id}",
                {
                    'type': 'typing_indicator',
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                    'is_typing': is_typing
                }
            )
    
    async def handle_read_receipt(self, data):
        message_id = data.get('message_id')
        
        if message_id:
            # Mark message as read
            await self.mark_message_as_read(message_id)
            
            # Notify sender that message was read
            message = await self.get_message_sender(message_id)
            if message and message['sender_id'] != self.user.id:
                await self.channel_layer.group_send(
                    f"user_{message['sender_id']}",
                    {
                        'type': 'read_receipt',
                        'message_id': message_id,
                        'read_by_id': self.user.id,
                        'read_by_username': self.user.username
                    }
                )
    
    async def handle_get_chat_history(self, data):
        other_user_id = data.get('user_id')
        
        if other_user_id:
            messages = await self.get_chat_history(other_user_id)
            await self.send(text_data=json.dumps({
                'type': 'chat_history',
                'messages': messages
            }))

    async def handle_get_friends_list(self, data):
        friends = await self.get_user_friends()
        await self.send(text_data=json.dumps({
            'type': 'friends_list',
            'friends': friends
        }))
    
    # WebSocket event handlers (called by group_send)
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username']
        }))
    
    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing_indicator',
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'is_typing': event['is_typing']
        }))
    
    async def read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'read_by_id': event['read_by_id'],
            'read_by_username': event['read_by_username']
        }))
    
    # Database operations
    @database_sync_to_async
    def update_online_status(self, is_online):
        try:
            profile = self.user.userprofile
            profile.is_online = is_online
            profile.last_seen = timezone.now() if not is_online else None
            profile.save()
        except Exception as e:
            logger.error(f"Error updating online status: {e}")
    
    @database_sync_to_async
    def save_chat_message(self, recipient_id, content, message_type):
        from django.contrib.auth import get_user_model
        from .models import ChatRoom, ChatMessage
        
        User = get_user_model()
        try:
            recipient = User.objects.get(id=recipient_id)
            
            # Get or create chat room
            chat_room = ChatRoom.get_or_create_room(self.user, recipient)
            
            # Save message
            message = ChatMessage.objects.create(
                chat_room=chat_room,
                sender=self.user,
                content=content,
                message_type=message_type
            )
            
            # Update room's updated_at timestamp
            chat_room.save()  # This triggers auto_now update
            
            return {
                'id': message.id,
                'content': message.content,
                'message_type': message.message_type,
                'sent_at': message.sent_at.isoformat(),
                'sender_id': message.sender.id,
                'sender_username': message.sender.username
            }
        except User.DoesNotExist:
            logger.error(f"Recipient user {recipient_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error saving chat message: {e}")
            return None
    
    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        from .models import ChatMessage
        try:
            message = ChatMessage.objects.get(id=message_id)
            if message.chat_room.participants.filter(id=self.user.id).exists():
                message.is_read = True
                message.save()
                return True
        except ChatMessage.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error marking message as read: {e}")
            return False
    
    @database_sync_to_async
    def get_message_sender(self, message_id):
        from .models import ChatMessage
        try:
            message = ChatMessage.objects.get(id=message_id)
            return {
                'sender_id': message.sender.id,
                'sender_username': message.sender.username
            }
        except ChatMessage.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_chat_history(self, other_user_id):
        from django.contrib.auth import get_user_model
        from .models import ChatRoom, ChatMessage
        
        User = get_user_model()
        try:
            other_user = User.objects.get(id=other_user_id)
            chat_room = ChatRoom.get_or_create_room(self.user, other_user)
            
            messages = ChatMessage.objects.filter(chat_room=chat_room).order_by('sent_at')
            
            return [{
                'id': msg.id,
                'content': msg.content,
                'message_type': msg.message_type,
                'sent_at': msg.sent_at.isoformat(),
                'sender_id': msg.sender.id,
                'sender_username': msg.sender.username,
                'is_read': msg.is_read
            } for msg in messages]
        except User.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    @database_sync_to_async
    def get_user_friends(self):
        try:
            # Get friends from UserProfile following field
            friends = self.user.userprofile.following.all()
            return [{
                'id': friend.user.id,
                'username': friend.user.username,
                'avatar': friend.avatar,
                'is_online': friend.is_online,
                'last_seen': friend.last_seen.isoformat() if friend.last_seen else None
            } for friend in friends]
        except Exception as e:
            logger.error(f"Error getting user friends: {e}")
            return []



class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Check if user is authenticated
        from django.contrib.auth.models import AnonymousUser
        if isinstance(self.scope['user'], AnonymousUser):
            await self.close()
            return
            
        self.user = self.scope['user']
        self.user_group_name = f"user_{self.user.id}"

        # Join user's personal group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()
        
        logger.info(f"Notification WebSocket connected for user {self.user.username}")
    
    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        logger.info(f"Notification WebSocket disconnected for user {getattr(self, 'user', 'unknown')}")
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_as_read':
                await self.handle_mark_as_read(data)
            elif message_type == 'get_notifications':
                await self.handle_get_notifications(data)
            elif message_type == 'get_notification_count':
                await self.handle_get_notification_count(data)
            else:
                logger.warning(f"Unknown notification message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error handling notification message: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': 'Server error'
            }))
    

    async def handle_get_notification_count(self, data):
        count = await self.get_unread_notification_count()
        await self.send(text_data=json.dumps({
            'type': 'notification_count',
            'count': count
        }))

    async def handle_mark_as_read(self, data):
        notification_id = data.get('notification_id')
        
        if notification_id:
            success = await self.mark_notification_as_read(notification_id)
            if success:
                await self.send(text_data=json.dumps({
                    'type': 'notification_marked_read',
                    'notification_id': notification_id
                }))
    
    async def handle_get_notifications(self, data):
        limit = data.get('limit', 20)
        notifications = await self.get_user_notifications(limit)
        
        await self.send(text_data=json.dumps({
            'type': 'notifications_list',
            'notifications': notifications
        }))
    
    # WebSocket event handlers (called by group_send)
    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))
    
    async def notification_count_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification_count_update',
            'count': event['count']
        }))
    
    # Database operations
    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        from .models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False
    
    @database_sync_to_async
    def get_user_notifications(self, limit=20):
        from .models import Notification
        try:
            notifications = Notification.objects.filter(
                user=self.user
            ).order_by('-created_at')[:limit]
            
            return [{
                'id': notif.id,
                'type': notif.type,
                'title': notif.title,
                'message': notif.message,
                'is_read': notif.is_read,
                'created_at': notif.created_at.isoformat(),
                'link': notif.link,
                'related_user_id': notif.related_user.id if notif.related_user else None,
                'related_user_username': notif.related_user.username if notif.related_user else None,
                'related_room_id': notif.related_room.id if notif.related_room else None,
                'related_room_title': notif.related_room.title if notif.related_room else None
            } for notif in notifications]
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []
        
    @database_sync_to_async
    def get_unread_notification_count(self):
        from .models import Notification
        try:
            return Notification.objects.filter(
                user=self.user,
                is_read=False
            ).count()
        except Exception as e:
            logger.error(f"Error getting notification count: {e}")
            return 0
# sample comment