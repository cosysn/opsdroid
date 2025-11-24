"""A connector for Wechat."""

import asyncio
import logging

import aiohttp

from opsdroid import events
from opsdroid.connector import Connector, register_event
from opsdroid.events import BanUser, DeleteMessage, JoinRoom, LeaveRoom, Message
from opsdroid.connector.wechat.client import AsyncWeChatClient

from wechatpy.enterprise import create_reply, parse_message
from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.enterprise.exceptions import InvalidCorpIdException
from wechatpy.exceptions import InvalidSignatureException, WeChatClientException


_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = {
    "bot-name": str,
}

class ConnectorWechat(Connector):
    """A connector for Wechat."""

    def __init__(self, config, opsdroid=None):
        """Create the connector."""
        super().__init__(config, opsdroid=opsdroid)
        _LOGGER.info(_("Starting Wechat connector."))
        self.name = "wechat"
        self.bot_name = config.get("bot-name", "opsdroid")
        self.corp_id = config.get("corp_id")
        self.secret = config.get("secret")
        self.agent_id = config.get("agent_id")
        self.token = config.get("token")
        self.aes_key = config.get("aes_key")
        _LOGGER.info("wechat init: corp_id: {}, secret: {}, agent_id: {}, token: {}, aes_key: {}".format(self.corp_id, 
            self.secret, self.agent_id, self.token, self.aes_key))
        self.opsdroid = opsdroid
        self.webhook_endpoint = f"/connector/{self.name}"
        self.crypto = WeChatCrypto(self.token, self.aes_key, self.corp_id)
        self.client = AsyncWeChatClient(self.corp_id, self.secret)

        self._event_queue = asyncio.Queue()
        self._event_queue_task = None

    async def connect(self):
        """Connect to the chat service."""
        _LOGGER.info(_("Connecting to Wechat."))

        # 启动异步客户端的token刷新任务
        await self.client.start_refresh_task()
        
        # 测试连接
        await self.client.ensure_valid_token()
        _LOGGER.info(f"Successfully connected to WeChat Work, agent_id: {self.agent_id}")

        # Create a task for background processing events received by
        # the web event handler.
        self._event_queue_task = asyncio.create_task(self._queue_worker())

        # Setup routes for webhooks subscription
        self.opsdroid.web_server.web_app.router.add_get(
            f"/connector/{self.name}", self.wechat_challenge_handler
        )
        self.opsdroid.web_server.web_app.router.add_post(
            f"/connector/{self.name}", self.wechat_message_handler
        )
    
    async def wechat_challenge_handler(self, request):
        """Handle the verification challenge from Wechat."""
        _LOGGER.info(_("Handling Wechat challenge."))
        
        try:
            msg_signature = request.query.get("msg_signature", "")
            timestamp = request.query.get("timestamp", "")
            nonce = request.query.get("nonce", "")
            
            if request.method == "GET":
                echo_str = request.query.get("echostr", "")
                if not all([msg_signature, timestamp, nonce, echo_str]):
                    return aiohttp.web.Response(text="Missing parameters", status=400)
                
                try:
                    echo_str = self.crypto.check_signature(
                        msg_signature, timestamp, nonce, echo_str
                    )
                    return aiohttp.web.Response(text=echo_str)
                except InvalidSignatureException:
                    return aiohttp.web.Response(text="Invalid signature", status=403)
            else:
                return aiohttp.web.Response(text="Method not allowed", status=405)
        except Exception as e:
            _LOGGER.error(f"Error processing webhook: {e}")
            return aiohttp.web.Response(text=f"Server error: {str(e)}", status=500)
        return aiohttp.web.Response(text="Challenge handled")
    
    async def _queue_worker(self):
        while True:
            payload = await self._event_queue.get()
            try:
                await self.event_handler(payload)
            finally:
                self._event_queue.task_done()
    
    async def event_handler(self, message):
        """Handle different payload types and parse the resulting events"""

        _LOGGER.info(message)

        try:
            # 获取发送者信息
            user_id = message.source
            _LOGGER.debug(f"Received message from {user_id}: {message}")
            
            # 处理不同类型的事件和消息
            if message.type == "text":
                await self._handle_text_message(user_id, message)
            # 可以添加更多事件处理...
            
        except Exception as e:
            _LOGGER.error(f"Error handling message: {e}")
    
    async def _handle_text_message(self, user_id, message):
        """处理文本消息"""
        text = message.content
        
        # 创建opsdroid消息对象
        opsdroid_message = Message(
            text=text,
            user=user_id,
            target=message.target,
            connector=self,
            raw_event=message
        )
        
        # 触发opsdroid技能处理
        await self.opsdroid.parse(opsdroid_message)

    async def wechat_message_handler(self, request):
        """Handle incoming message from Wechat."""
        _LOGGER.info(_("Handling Wechat message."))
        try:
            msg_signature = request.query.get("msg_signature", "")
            timestamp = request.query.get("timestamp", "")
            nonce = request.query.get("nonce", "")
            
            if request.method == "POST":
                body = await request.read()
                if not body:
                    return aiohttp.web.Response(text="Empty body", status=400)
                
                try:
                    if self.crypto:
                        decrypted_xml = self.crypto.decrypt_message(
                            body, msg_signature, timestamp, nonce
                        )
                    else:
                        decrypted_xml = body.decode('utf-8')
                    
                    msg = parse_message(decrypted_xml)
                    _LOGGER.info("[wechat] receive message: {}, msg= {}".format(decrypted_xml, msg))

                    # Put the event in the queue to process it in the background and
                    # immediately acknowledge the reception by returning status code 200.
                    # Slack will resend events that have not been acknowledged within 3
                    # seconds and we want to avoid that.
                    #
                    # https://api.slack.com/apis/connections/events-api#the-events-api__responding-to-events
                    self._event_queue.put_nowait(msg)
                    
                    return aiohttp.web.Response(text="success")
                except InvalidSignatureException:
                    return aiohttp.web.Response(text="Invalid signature", status=403)
                except Exception as e:
                    _LOGGER.error(f"Error decrypting message: {e}")
                    return aiohttp.web.Response(text="Decryption error", status=500)
            
            else:
                return aiohttp.web.Response(text="Method not allowed", status=405)
                
        except Exception as e:
            _LOGGER.error(f"Error processing webhook: {e}")
            return aiohttp.web.Response(text=f"Server error: {str(e)}", status=500)

    async def disconnect(self):
        """Disconnect from Slack.

        Cancels the event queue worker task and disconnects the
        socket_mode_client if socket mode was enabled."""

        _LOGGER.info(_("Disconnect to Wechat."))
        if self._event_queue_task:
            self._event_queue_task.cancel()
            await asyncio.gather(self._event_queue_task, return_exceptions=True)

    async def listen(self):
        """Listen for and parse new messages."""
        _LOGGER.info(_("Listening to Wechat."))
        while True:
            await asyncio.sleep(3600)

    @register_event(events.Message)
    async def _send_message(self, message):
        """Respond with a message."""
        
        _LOGGER.info(
            _("Responding with: '%s' in room  %s from %s."), message.text, message.target, message.user
        )
        
        try:
            result = await self.client.send_text(self.agent_id, message.user, message.text)
            return result
        except WeChatClientException as e:
            _LOGGER.error(f"Failed to send text message: {e}")
            raise
