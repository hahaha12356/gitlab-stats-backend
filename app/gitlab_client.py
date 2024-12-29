import requests
from datetime import datetime
import logging
import os
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket
from urllib.parse import urlparse

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class GitLabClient:
    def __init__(self, base_url, private_token):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'PRIVATE-TOKEN': private_token,
            'Content-Type': 'application/json'
        }
        
        # 创建不使用代理的session
        self.session = requests.Session()
        # 显式禁用所有代理
        self.session.proxies = {
            'http': None,
            'https': None
        }
        
        self.request_kwargs = {
            'verify': False,
            'timeout': 30
        }
        
        logger.debug(f"Initialized GitLab client with base URL: {self.base_url}")
        logger.debug(f"Session proxies: {self.session.proxies}")
    
    def _test_proxy(self):
        """测试代理连接"""
        try:
            proxy = self.session.proxies.get('http', '').replace('http://', '')
            if proxy:
                host, port = proxy.split(':')
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((host, int(port)))
                sock.close()
                logger.info(f"Successfully connected to proxy {proxy}")
                # 测试代理是否可用
                test_url = 'http://www.google.com'
                logger.debug(f"Testing proxy with {test_url}")
                response = requests.get(test_url, proxies=self.session.proxies, timeout=5, verify=False)
                response.raise_for_status()
                logger.info("Proxy is working correctly")
        except Exception as e:
            logger.error(f"Failed to connect to proxy: {str(e)}")
            raise
    
    def _test_connection(self):
        """测试GitLab连接"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v4/version",
                **self.request_kwargs
            )
            response.raise_for_status()
            logger.info(f"Successfully connected to GitLab. Version: {response.json()}")
        except Exception as e:
            logger.error(f"Failed to connect to GitLab: {str(e)}")
            raise
    
    def get_group_projects(self, group_id):
        url = f"{self.base_url}/api/v4/groups/{group_id}/projects"
        logger.debug(f"Requesting projects for group {group_id} from: {url}")
        response = self.session.get(
            url, 
            headers=self.headers,
            **self.request_kwargs
        )
        
        # 打印响应状态和内容以便调试
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response content: {response.text}")
        
        # 检查响应状态
        response.raise_for_status()
        
        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response content: {response.text}")
            raise
    
    def get_project_commits(self, project_id, since=None, until=None):
        """获取项目的commits"""
        # 首先验证项目是否存在
        try:
            project_url = f"{self.base_url}/api/v4/projects/{project_id}"
            logger.debug(f"Verifying project existence: {project_url}")
            
            response = self.session.get(
                project_url,
                headers=self.headers,
                **self.request_kwargs
            )
            
            if response.status_code == 404:
                logger.error(f"Project {project_id} not found")
                raise Exception(f"Project {project_id} not found")
            response.raise_for_status()
            
            project_info = response.json()
            logger.debug(f"Found project: {project_info.get('name', 'Unknown')}")

            # 尝试不同的API路径
            api_paths = [
                f"/api/v4/projects/{project_id}/repository/commits",  # 尝试repository路径
                f"/api/v4/projects/{project_id}/commits"             # 原始路径
            ]
            
            last_error = None
            for path in api_paths:
                try:
                    url = f"{self.base_url}{path}"
                    params = {}
                    if since:
                        params['since'] = since
                    if until:
                        params['until'] = until

                    logger.debug(f"Trying commits API path: {url}")
                    response = self.session.get(
                        url,
                        headers=self.headers,
                        params=params,
                        **self.request_kwargs
                    )
                    
                    if response.status_code == 200:
                        return response.json()
                        
                except Exception as e:
                    last_error = e
                    continue
                
            # 如果所有路径都失败
            raise Exception(f"Unable to get commits using any available API path: {str(last_error)}")

        except Exception as e:
            logger.error(f"Error in get_project_commits: {str(e)}")
            raise
    
    def get_project_merge_requests(self, project_id, state='merged', since=None, until=None):
        url = f"{self.base_url}/api/v4/projects/{project_id}/merge_requests"
        params = {'state': state}
        if since:
            params['created_after'] = since
        if until:
            params['created_before'] = until
            
        logger.debug(f"Requesting merge requests from: {url} with params: {params}")
        response = self.session.get(
            url, 
            headers=self.headers, 
            params=params,
            **self.request_kwargs
        )
        response.raise_for_status()
        return response.json() 