import asyncio
import time
import logging
from wechatpy.enterprise import WeChatClient
from wechatpy.exceptions import WeChatClientException

_LOGGER = logging.getLogger(__name__)


class AsyncWeChatClient:
    """异步企业微信客户端"""
    
    def __init__(self, corp_id, secret, access_token=None, session=None, timeout=None, auto_retry=True):
        self.corp_id = corp_id
        self.secret = secret
        
        self._client = WeChatClient(
            corp_id, secret, access_token, session, timeout, auto_retry
        )
        
        self._access_token = None
        self._token_expires_at = None
        
        self._refresh_lock = asyncio.Lock()
        self._refresh_task = None
        self._should_refresh = True
        
        _LOGGER.debug(f"Initialized AsyncWeChatClient with corp_id: {corp_id}")
    
    async def _run_in_threadpool(self, func, *args, **kwargs):
        """使用默认线程池执行同步函数"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: func(*args, **kwargs)
        )
    
    async def start_refresh_task(self):
        """启动主动刷新的后台任务"""
        if self._refresh_task is None:
            # 首次启动时强制获取一次 token
            await self.ensure_valid_token()
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
                # 检查是否需要刷新 token
                if self._access_token is None or self._token_expires_at is None or self._token_expires_at - time.time() < 600:
                    _LOGGER.info(f"Token needs refresh - expires_at: {self._token_expires_at}")
                    async with self._refresh_lock:
                        # 双重检查避免重复刷新
                        if self._access_token is None or self._token_expires_at is None or self._token_expires_at - time.time() < 600:
                            await self._refresh_token()
                else:
                    _LOGGER.info(f"Token is still valid, no need refresh token- expires_at: {self._token_expires_at}")
                
                # 每次检查间隔60秒
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error in refresh loop: {e}")
                await asyncio.sleep(60)
    
    async def _refresh_token(self):
        """刷新 access_token"""
        try:
            _LOGGER.info("Refreshing access token...")
            
            # 使用 wechatpy 的 access_token 属性获取 token
            # 这会触发 wechatpy 内部的获取逻辑，包括保存到 session
            access_token = await self._run_in_threadpool(
                lambda: self._client.access_token
            )
            
            # 手动设置过期时间（企业微信 token 有效期为 7200 秒）
            self._access_token = access_token
            self._token_expires_at = self.client.expires_at  # 使用 wechatpy 提供的过期时间
            
            _LOGGER.info(f"Successfully refreshed access token, expires_at: {self._token_expires_at}")
            
            return access_token
        except WeChatClientException as e:
            _LOGGER.error(f"Failed to refresh access token: {e}")
            raise
    
    async def ensure_valid_token(self):
        """确保 token 有效"""
        # 如果 token 不存在或已过期，则刷新
        if self._access_token is None or self._token_expires_at is None or self._token_expires_at - time.time() < 60:
            async with self._refresh_lock:
                # 双重检查
                if self._access_token is None or self._token_expires_at is None or self._token_expires_at - time.time() < 60:
                    await self._refresh_token()
        else:
            _LOGGER.info("[ensure_valid_token] Access token is still valid, no need to refresh")
        return self._access_token
    
    # 消息发送方法 - 保持与 WeChatClient 相同的接口名称
    async def send_text(self, agent_id, user_id, content):
        """发送文本消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_text,
            agent_id, user_id, content
        )
    
    async def send_image(self, agent_id, user_id, media_id):
        """发送图片消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_image,
            agent_id, user_id, media_id
        )
    
    async def send_voice(self, agent_id, user_id, media_id):
        """发送语音消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_voice,
            agent_id, user_id, media_id
        )
    
    async def send_video(self, agent_id, user_id, media_id, title=None, description=None):
        """发送视频消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_video,
            agent_id, user_id, media_id, title, description
        )
    
    async def send_file(self, agent_id, user_id, media_id):
        """发送文件消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_file,
            agent_id, user_id, media_id
        )
    
    async def send_text_card(self, agent_id, user_id, title, description, url, btntxt=None):
        """发送文本卡片消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_text_card,
            agent_id, user_id, title, description, url, btntxt
        )
    
    async def send_news(self, agent_id, user_id, articles):
        """发送图文消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_news,
            agent_id, user_id, articles
        )
    
    async def send_mpnews(self, agent_id, user_id, articles):
        """发送加密图文消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_mpnews,
            agent_id, user_id, articles
        )
    
    async def send_markdown(self, agent_id, user_id, content):
        """发送 Markdown 消息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.message.send_markdown,
            agent_id, user_id, content
        )
    
    # 用户管理方法
    async def get_user(self, user_id):
        """获取用户信息"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.user.get,
            user_id
        )
    
    async def get_department_users(self, department_id, fetch_child=False, status=0, simple=False):
        """获取部门成员"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.user.get_department_users,
            department_id, fetch_child, status, simple
        )
    
    # 媒体文件管理
    async def upload_media(self, media_type, media_file):
        """上传临时素材"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.media.upload,
            media_type, media_file
        )
    
    async def get_media(self, media_id):
        """获取临时素材"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.media.get,
            media_id
        )
    
    async def upload_image(self, image_file):
        """上传图片"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.media.upload_image,
            image_file
        )
    
    async def get_image(self, media_id):
        """获取图片"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
            self._client.media.get,
            media_id
        )
    
    # 消息解析
    async def parse_message(self, xml_content):
        """解析消息"""
        return await self._run_in_threadpool(
            self._client.message.parse_message,
            xml_content
        )
    
    # 部门管理
    async def get_departments(self, department_id=None):
        """获取部门列表"""
        await self.ensure_valid_token()
        return await self._run_in_threadpool(
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