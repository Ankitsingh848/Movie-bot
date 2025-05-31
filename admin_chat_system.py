import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from database import Database
from config import Config
from datetime import datetime

logger = logging.getLogger(__name__)

class AdminChatSystem:
    """Hidden admin chat system for customer support"""
    
    def __init__(self, database: Database):
        self.db = database
        self.active_chats = {}  # {user_id: {'admin_id': admin_id, 'started_at': datetime}}
    
    async def start_admin_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start hidden admin chat session"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use admin chat.")
            return
        
        keyboard = [
            [InlineKeyboardButton("👥 View Active Users", callback_data="adminchat_users")],
            [InlineKeyboardButton("💬 Chat with User", callback_data="adminchat_start")],
            [InlineKeyboardButton("📋 Chat History", callback_data="adminchat_history")],
            [InlineKeyboardButton("❌ End All Chats", callback_data="adminchat_end_all")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        active_count = len(self.active_chats)
        chat_text = (
            f"🔐 **Hidden Admin Chat System**\n\n"
            f"**Status:**\n"
            f"• Active Chats: {active_count}\n"
            f"• Online Admins: {len(Config.ADMIN_IDS)}\n"
            f"• Total Users: {self._get_total_users()}\n\n"
            f"**Features:**\n"
            f"• Chat anonymously with users\n"
            f"• Help users without revealing admin identity\n"
            f"• Monitor user conversations\n"
            f"• Provide instant support\n\n"
            f"**Select an option:**"
        )
        
        await update.message.reply_text(
            chat_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_admin_chat_callback(self, query, context):
        """Handle admin chat callbacks"""
        data = query.data
        user = query.from_user
        
        if user.id not in Config.ADMIN_IDS:
            await query.answer("❌ Not authorized", show_alert=True)
            return
        
        try:
            if data == "adminchat_users":
                await self._show_active_users(query, context)
            elif data == "adminchat_start":
                await self._start_chat_with_user(query, context)
            elif data == "adminchat_history":
                await self._show_chat_history(query, context)
            elif data == "adminchat_end_all":
                await self._end_all_chats(query, context)
            elif data.startswith("adminchat_connect_"):
                user_id = int(data.split("_")[2])
                await self._connect_to_user(query, context, user_id)
            elif data.startswith("adminchat_end_"):
                user_id = int(data.split("_")[2])
                await self._end_chat_with_user(query, context, user_id)
            elif data == "adminchat_back":
                await self._show_admin_chat_menu(query, context)
        except Exception as e:
            logger.error(f"Error in admin chat callback: {e}")
            await query.edit_message_text("❌ An error occurred in admin chat system.")
    
    async def _show_active_users(self, query, context):
        """Show list of active users for chat"""
        # Get recent users from database
        recent_users = self.db.get_recent_user_messages(limit=20)
        
        keyboard = []
        user_text = "👥 **Active Users**\n\n"
        
        if recent_users:
            for i, user_msg in enumerate(recent_users[:10]):
                user_id = user_msg['user_id']
                username = user_msg['username'] or f"User_{user_id}"
                last_msg = user_msg['message_text'][:30] + "..." if len(user_msg['message_text']) > 30 else user_msg['message_text']
                
                user_text += f"{i+1}. @{username} (ID: {user_id})\n"
                user_text += f"   Last: {last_msg}\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"💬 Chat with @{username}",
                    callback_data=f"adminchat_connect_{user_id}"
                )])
        else:
            user_text += "No recent user activity found."
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adminchat_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            user_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _start_chat_with_user(self, query, context):
        """Start chat by entering user ID"""
        await query.edit_message_text(
            "💬 **Start Hidden Chat**\n\n"
            "Send the user's ID or username to start chatting.\n"
            "Format: `/chat 123456789` or `/chat @username`\n\n"
            "You will appear as 'Support Bot' to the user.\n"
            "They won't know you're an admin.",
            parse_mode='Markdown'
        )
    
    async def _connect_to_user(self, query, context, user_id):
        """Connect admin to specific user"""
        admin_id = query.from_user.id
        
        # Start chat session
        self.active_chats[user_id] = {
            'admin_id': admin_id,
            'started_at': datetime.now()
        }
        
        # Notify admin
        await query.edit_message_text(
            f"✅ **Connected to User {user_id}**\n\n"
            f"You are now chatting with this user as 'Support Bot'.\n"
            f"All your messages will be forwarded to them anonymously.\n\n"
            f"**Commands:**\n"
            f"• Type normally to send messages\n"
            f"• `/endchat` to end this session\n"
            f"• `/chatinfo` to see user details\n\n"
            f"Start typing your message...",
            parse_mode='Markdown'
        )
        
        # Notify user that support is available
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🤖 **Support Bot Connected**\n\n"
                     "Hi! I'm here to help you with any questions.\n"
                     "Feel free to ask anything about the bot or movies!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Could not notify user {user_id}: {e}")
    
    async def _show_chat_history(self, query, context):
        """Show recent chat history"""
        # Get recent messages
        messages = self.db.get_recent_user_messages(limit=50)
        
        history_text = "📋 **Recent Chat History**\n\n"
        
        if messages:
            for msg in messages[:20]:
                username = msg['username'] or f"User_{msg['user_id']}"
                msg_text = msg['message_text'][:50] + "..." if len(msg['message_text']) > 50 else msg['message_text']
                history_text += f"👤 @{username}: {msg_text}\n"
        else:
            history_text += "No chat history found."
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="adminchat_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _end_all_chats(self, query, context):
        """End all active chat sessions"""
        count = len(self.active_chats)
        
        # Notify all users
        for user_id in list(self.active_chats.keys()):
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🤖 Support session ended. Thank you for using our service!"
                )
            except:
                pass
        
        self.active_chats.clear()
        
        await query.edit_message_text(
            f"✅ **All Chats Ended**\n\n"
            f"Closed {count} active chat sessions.\n"
            f"All users have been notified.",
            parse_mode='Markdown'
        )
    
    async def _show_admin_chat_menu(self, query, context):
        """Show main admin chat menu"""
        keyboard = [
            [InlineKeyboardButton("👥 View Active Users", callback_data="adminchat_users")],
            [InlineKeyboardButton("💬 Chat with User", callback_data="adminchat_start")],
            [InlineKeyboardButton("📋 Chat History", callback_data="adminchat_history")],
            [InlineKeyboardButton("❌ End All Chats", callback_data="adminchat_end_all")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        active_count = len(self.active_chats)
        chat_text = (
            f"🔐 **Hidden Admin Chat System**\n\n"
            f"**Status:**\n"
            f"• Active Chats: {active_count}\n"
            f"• Online Admins: {len(Config.ADMIN_IDS)}\n"
            f"• Total Users: {self._get_total_users()}\n\n"
            f"**Select an option:**"
        )
        
        await query.edit_message_text(
            chat_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages from admin during chat session"""
        admin_id = update.effective_user.id
        
        if admin_id not in Config.ADMIN_IDS:
            return False
        
        # Check if admin is in active chat
        user_id = None
        for uid, chat_info in self.active_chats.items():
            if chat_info['admin_id'] == admin_id:
                user_id = uid
                break
        
        if not user_id:
            return False
        
        # Forward message to user as "Support Bot"
        try:
            message_text = update.message.text
            
            # Handle special commands
            if message_text.startswith('/endchat'):
                await self._end_chat_with_user_direct(update, context, user_id)
                return True
            elif message_text.startswith('/chatinfo'):
                await self._show_user_info(update, context, user_id)
                return True
            
            # Forward normal message
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🤖 **Support Bot:** {message_text}",
                parse_mode='Markdown'
            )
            
            # Confirm to admin
            await update.message.reply_text(
                f"✅ Message sent to User {user_id}",
                parse_mode='Markdown'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error forwarding admin message: {e}")
            await update.message.reply_text("❌ Failed to send message to user.")
            return True
    
    async def handle_user_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages from users during chat session"""
        user_id = update.effective_user.id
        
        if user_id not in self.active_chats:
            return False
        
        # Forward message to admin
        try:
            admin_id = self.active_chats[user_id]['admin_id']
            username = update.effective_user.username or f"User_{user_id}"
            message_text = update.message.text
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"💬 **@{username} (ID: {user_id}):** {message_text}",
                parse_mode='Markdown'
            )
            
            # Auto-reply to user
            await update.message.reply_text(
                "🤖 Message received! Support will respond shortly.",
                parse_mode='Markdown'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error forwarding user message: {e}")
            return False
    
    async def _end_chat_with_user_direct(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """End chat session directly from admin"""
        if user_id in self.active_chats:
            del self.active_chats[user_id]
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🤖 Support session ended. Thank you!"
                )
            except:
                pass
            
            await update.message.reply_text(
                f"✅ Chat with User {user_id} ended.",
                parse_mode='Markdown'
            )
    
    async def _show_user_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show user information to admin"""
        try:
            # Get user stats
            stats = self.db.get_stats()
            user_messages = self.db.get_recent_user_messages(limit=100)
            user_specific = [msg for msg in user_messages if msg['user_id'] == user_id]
            
            info_text = (
                f"👤 **User Information**\n\n"
                f"**User ID:** {user_id}\n"
                f"**Messages Sent:** {len(user_specific)}\n"
                f"**Chat Started:** {self.active_chats[user_id]['started_at'].strftime('%H:%M:%S')}\n\n"
                f"**Recent Activity:**\n"
            )
            
            for msg in user_specific[:5]:
                msg_text = msg['message_text'][:30] + "..." if len(msg['message_text']) > 30 else msg['message_text']
                info_text += f"• {msg_text}\n"
            
            await update.message.reply_text(info_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting user info: {e}")
    
    def _get_total_users(self):
        """Get total number of users"""
        try:
            stats = self.db.get_stats()
            return stats.get('total_users', 0)
        except:
            return 0