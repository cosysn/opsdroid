import asyncio
import time
import logging
from wechatpy.enterprise import WeChatClient
from wechatpy.exceptions import WeChatClientException

_LOGGER = logging.getLogger(__name__)

class AsyncWeChatClient:
    """异步企业微信客户端，支持自动刷新 access_token"""
    
    def __init__(self, corp_id, secret, access_token=None, session=None, timeout=None, auto_retry=True):
        # 使用组合而非继承
        self._client = WeChatClient(corp_id, secret, access_token, session, timeout, auto_retry)
        self.corp_id = corp_id
        self._refresh_lock = asyncio.Lock()
        self._refresh_task = None
        self._should_refresh = True
        
    async def start_refresh_task(self):
        """启动主动刷新的后台任务"""
        if self._refresh_task is None:
            self._refresh_task = asyncio.create_task(self._refresh_loop())
            _LOGGER.info("Started WeChat access token refresh task")
    
    async def stop_refresh_task(self):
        """停止刷新任务"""
        self._should_refresh = False
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
            _LOGGER.info("Stopped WeChat access token refresh task")
    
    async def _refresh_loop(self):
        """刷新 access_token 的循环任务"""
        while self._should_refresh:
            try:
                now = time.time()
                expires_at = self._client.session.get(f"{self.corp_id}_expires_at", 0)
                
                # 提前10分钟刷新(600秒)
                if expires_at - now < 600:
                    async with self._refresh_lock:
                        # 双重检查避免重复刷新
                        current_expires_at = self._client.session.get(f"{self.corp_id}_expires_at", 0)
                        if current_expires_at - time.time() < 600:
                            await self._async_fetch_access_token()
                
                # 每次检查间隔60秒
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error in refresh loop: {e}")
                await asyncio.sleep(60)  # 出错后等待60秒再重试
    
    async def _async_fetch_access_token(self):
        """异步获取 access_token"""
        try:
            # 使用线程池执行同步的 fetch_access_token 方法
            _LOGGER.info("Start refresh WeChat access token")
            loop = asyncio.get_event_loop()
            access_token = await loop.run_in_executor(
                None, 
                self._client.fetch_access_token
            )
            _LOGGER.info("Successfully refreshed WeChat access token")
            return access_token
        except WeChatClientException as e:
            _LOGGER.error(f"Failed to refresh access token: {e}")
            raise
    
    async def fetch_access_token(self):
        """获取 access_token（保持与 WeChatClient 相同的接口）"""
        async with self._refresh_lock:
            access_token_key = f"{self.corp_id}_access_token"
            access_token = self._client.session.get(access_token_key)
            expires_at = self._client.session.get(f"{self.corp_id}_expires_at", 0)
            
            if access_token and expires_at > time.time() + 60:
                return access_token
            return await self._async_fetch_access_token()
    
    async def ensure_valid_token(self):
        """确保 token 有效"""
        return await self.fetch_access_token()
    
    # 消息发送方法 - 保持与 WeChatClient 相同的接口名称
    async def send_text(self, agent_id, user_id, content):
        """发送文本消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_text,
            agent_id, user_id, content
        )
    
    async def send_image(self, agent_id, user_id, media_id):
        """发送图片消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_image,
            agent_id, user_id, media_id
        )
    
    async def send_voice(self, agent_id, user_id, media_id):
        """发送语音消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_voice,
            agent_id, user_id, media_id
        )
    
    async def send_video(self, agent_id, user_id, media_id, title=None, description=None):
        """发送视频消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_video,
            agent_id, user_id, media_id, title, description
        )
    
    async def send_file(self, agent_id, user_id, media_id):
        """发送文件消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_file,
            agent_id, user_id, media_id
        )
    
    async def send_text_card(self, agent_id, user_id, title, description, url, btntxt=None):
        """发送文本卡片消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_text_card,
            agent_id, user_id, title, description, url, btntxt
        )
    
    async def send_news(self, agent_id, user_id, articles):
        """发送图文消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_news,
            agent_id, user_id, articles
        )
    
    async def send_mpnews(self, agent_id, user_id, articles):
        """发送加密图文消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_mpnews,
            agent_id, user_id, articles
        )
    
    async def send_markdown(self, agent_id, user_id, content):
        """发送 Markdown 消息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.send_markdown,
            agent_id, user_id, content
        )
    
    # 用户管理方法
    async def get_user(self, user_id):
        """获取用户信息"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.user.get,
            user_id
        )
    
    async def get_department_users(self, department_id, fetch_child=False, status=0, simple=False):
        """获取部门成员"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.user.get_department_users,
            department_id, fetch_child, status, simple
        )
    
    # 媒体文件管理
    async def upload_media(self, media_type, media_file):
        """上传临时素材"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.media.upload,
            media_type, media_file
        )
    
    async def get_media(self, media_id):
        """获取临时素材"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.media.get,
            media_id
        )
    
    async def upload_image(self, image_file):
        """上传图片"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.media.upload_image,
            image_file
        )
    
    async def get_image(self, media_id):
        """获取图片"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.media.get,
            media_id
        )
    
    # 消息解析
    async def parse_message(self, xml_content):
        """解析消息"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.message.parse_message,
            xml_content
        )
    
    # 部门管理
    async def get_departments(self, department_id=None):
        """获取部门列表"""
        await self.ensure_valid_token()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._client.department.get,
            department_id
        )
    
    # 访问内部客户端的方法（用于访问未封装的方法）
    @property
    def client(self):
        """获取内部 WeChatClient 实例（谨慎使用）"""
        return self._client
    
    @property
    def message(self):
        """获取消息 API"""
        return self
    
    @property
    def user(self):
        """获取用户 API"""
        return self
    
    @property
    def media(self):
        """获取媒体 API"""
        return self
    
    @property
    def department(self):
        """获取部门 API"""
        return self