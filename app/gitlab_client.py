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
        """获取组内所有项目
        
        Args:
            group_id: 组ID
        """
        url = f"{self.base_url}/api/v4/groups/{group_id}/projects"
        params = {'per_page': 100}  # 增加每页数量
        
        logger.info(f"Fetching projects for group {group_id}")
        
        all_projects = []
        page = 1
        
        while True:
            try:
                params['page'] = page
                logger.debug(f"Fetching page {page} of projects")
                
                response = self.session.get(
                    url,
                    headers=self.headers,
                    params=params,
                    **self.request_kwargs
                )
                response.raise_for_status()
                
                projects = response.json()
                if not projects:
                    break
                    
                all_projects.extend(projects)
                logger.debug(f"Found {len(projects)} projects on page {page}")
                
                # 检查是否有下一页
                if 'next' not in response.links:
                    break
                    
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching projects page {page}: {str(e)}")
                break
        
        logger.info(f"Total projects found: {len(all_projects)}")
        return all_projects
    
    def get_project_branches(self, project_id):
        """获取项目的所有分支"""
        url = f"{self.base_url}/api/v4/projects/{project_id}/repository/branches"
        params = {'per_page': 100}
        
        all_branches = []
        page = 1
        
        while True:
            try:
                params['page'] = page
                logger.debug(f"Fetching branches page {page} for project {project_id}")
                
                response = self.session.get(
                    url,
                    headers=self.headers,
                    params=params,
                    **self.request_kwargs
                )
                response.raise_for_status()
                
                branches = response.json()
                if not branches:
                    break
                    
                all_branches.extend(branches)
                logger.debug(f"Found {len(branches)} branches on page {page}")
                
                if 'next' not in response.links:
                    break
                    
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching branches page {page}: {str(e)}")
                break
        
        logger.info(f"Total branches found for project {project_id}: {len(all_branches)}")
        return all_branches
    
    def get_project_commits(self, project_id, since=None, until=None):
        """获取项目所有分支的commits"""
        try:
            # 验证项目存在
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

            # 获取所有分支
            branches = self.get_project_branches(project_id)
            all_commits = set()  # 使用集合去重
            
            for branch in branches:
                branch_name = branch['name']
                logger.debug(f"Fetching commits for branch: {branch_name}")
                
                page = 1
                while True:
                    try:
                        url = f"{self.base_url}/api/v4/projects/{project_id}/repository/commits"
                        params = {
                            'ref_name': branch_name,
                            'per_page': 100,
                            'page': page
                        }
                        
                        if since:
                            params['since'] = since
                        if until:
                            params['until'] = until

                        logger.debug(f"Requesting commits from branch {branch_name} (page {page})")
                        response = self.session.get(
                            url,
                            headers=self.headers,
                            params=params,
                            **self.request_kwargs
                        )
                        
                        if response.status_code == 200:
                            commits = response.json()
                            if not commits:
                                break
                                
                            # 使用commit id作为唯一标识添加到集合中
                            for commit in commits:
                                commit_tuple = (
                                    commit['id'],
                                    commit['author_name'],
                                    commit['authored_date'],
                                    commit['title']
                                )
                                all_commits.add(commit_tuple)
                                
                            logger.debug(f"Found {len(commits)} commits on page {page} for branch {branch_name}")
                            
                            if 'next' not in response.links:
                                break
                                
                            page += 1
                        else:
                            logger.warning(f"Failed to get commits for branch {branch_name}: {response.status_code}")
                            break
                            
                    except Exception as e:
                        logger.error(f"Error fetching commits for branch {branch_name} page {page}: {str(e)}")
                        break
            
            # 转换回列表格式，并重建完整的commit对象
            commits_list = [
                {
                    'id': commit_id,
                    'author_name': author_name,
                    'authored_date': authored_date,
                    'title': title
                }
                for commit_id, author_name, authored_date, title in all_commits
            ]
            
            logger.info(f"Total unique commits found across all branches: {len(commits_list)}")
            return commits_list

        except Exception as e:
            logger.error(f"Error in get_project_commits: {str(e)}")
            raise
    
    def get_project_merge_requests(self, project_id, state='all', since=None, until=None):
        """获取项目的merge requests"""
        url = f"{self.base_url}/api/v4/projects/{project_id}/merge_requests"
        params = {'state': state, 'per_page': 100}
        if since:
            params['created_after'] = since
        if until:
            params['created_before'] = until
        
        logger.debug(f"Requesting merge requests from: {url} with params: {params}")
        
        all_merge_requests = []
        page = 1
        
        while True:
            try:
                params['page'] = page
                # 移除额外的timeout参数，使用request_kwargs中的设置
                response = self.session.get(
                    url, 
                    headers=self.headers, 
                    params=params,
                    **self.request_kwargs
                )
                response.raise_for_status()
                
                merge_requests = response.json()
                if not merge_requests:
                    break
                    
                all_merge_requests.extend(merge_requests)
                logger.debug(f"Found {len(merge_requests)} merge requests on page {page}")
                
                if 'next' not in response.links:
                    break
                    
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching merge requests page {page}: {str(e)}")
                break
        
        logger.info(f"Total merge requests found: {len(all_merge_requests)}")
        return all_merge_requests 