from collections import defaultdict
from .gitlab_client import GitLabClient
import logging

logger = logging.getLogger(__name__)

class GitLabStatsService:
    def __init__(self, gitlab_client):
        self.client = gitlab_client
    
    def collect_stats(self, group_id, start_date, end_date):
        """收集统计数据"""
        projects = self.client.get_group_projects(group_id)
        stats = {
            'total_commits': 0,
            'total_merge_requests': 0,
            'total_projects': 0,  # 新增：项目总数
            'projects': [],
            'skipped_projects': [],
            'partial_data_projects': [],
            'contributors': defaultdict(lambda: {  # 新增：全局贡献者统计
                'commits': 0,
                'merge_requests': 0
            })
        }
        
        for project in projects:
            project_id = project['id']
            if project_id == 174:  # 跳过已知有问题的项目
                logger.warning(f"Skipping project ID 174 ({project.get('name', 'Unknown')})")
                stats['skipped_projects'].append({
                    'id': project_id,
                    'name': project.get('name', 'Unknown'),
                    'reason': 'Project ID temporarily excluded'
                })
                continue
            
            try:
                project_stats = self._collect_project_stats(project, start_date, end_date)
                
                # 转换为前端期望的格式
                formatted_stats = {
                    'id': project_stats['id'],
                    'name': project_stats['name'],
                    'commits': project_stats['commit_count'],
                    'merge_requests': project_stats['merge_request_count'],
                    'contributors': [
                        {
                            'name': author,
                            'commits': contributor_stats['commits'],
                            'merge_requests': contributor_stats['merge_requests']
                        }
                        for author, contributor_stats in project_stats['contributors'].items()
                    ]
                }
                
                # 更新全局贡献者统计
                for author, contributor_stats in project_stats['contributors'].items():
                    stats['contributors'][author]['commits'] += contributor_stats['commits']
                    stats['contributors'][author]['merge_requests'] += contributor_stats['merge_requests']
                
                if project_stats.get('errors'):
                    stats['partial_data_projects'].append({
                        'id': project_id,
                        'name': project.get('name', 'Unknown'),
                        'errors': project_stats['errors']
                    })
                
                stats['total_commits'] += project_stats['commit_count']
                stats['total_merge_requests'] += project_stats['merge_request_count']
                stats['projects'].append(formatted_stats)
                stats['total_projects'] += 1  # 增加项目计数
                
            except Exception as e:
                logger.error(f"Error collecting stats for project {project_id}: {str(e)}")
                stats['skipped_projects'].append({
                    'id': project_id,
                    'name': project.get('name', 'Unknown'),
                    'reason': str(e)
                })
                continue
        
        # 将defaultdict转换为普通dict
        stats['contributors'] = dict(stats['contributors'])
        return stats 
    
    def _collect_project_stats(self, project, start_date, end_date):
        """收集单个项目的统计数据"""
        project_stats = {
            'id': project['id'],
            'name': project['name'],
            'commit_count': 0,
            'merge_request_count': 0,
            'contributors': defaultdict(lambda: {
                'commits': 0,
                'merge_requests': 0
            }),
            'errors': [],  # 用于记录数据收集过程中的错误
            'status': {    # 新增: 记录数据获取状态
                'commits_available': False,
                'merge_requests_available': False
            }
        }
        
        # 尝试获取commits
        try:
            commits = self.client.get_project_commits(
                project['id'],
                since=start_date,
                until=end_date
            )
            project_stats['commit_count'] = len(commits)
            project_stats['status']['commits_available'] = True
            
            # 统计贡献者信息
            for commit in commits:
                author = commit['author_name']
                project_stats['contributors'][author]['commits'] += 1
        except Exception as e:
            logger.warning(f"Unable to get commits for project {project['id']}: {str(e)}")
            project_stats['errors'].append({
                'type': 'commits',
                'error': str(e)
            })
        
        # 尝试获取merge requests
        try:
            merge_requests = self.client.get_project_merge_requests(
                project['id'],
                since=start_date,
                until=end_date
            )
            project_stats['merge_request_count'] = len(merge_requests)
            project_stats['status']['merge_requests_available'] = True
            
            # 统计合并请求的贡献者信息
            for mr in merge_requests:
                if 'author' in mr and 'name' in mr['author']:
                    author = mr['author']['name']
                    project_stats['contributors'][author]['merge_requests'] += 1
        except Exception as e:
            logger.warning(f"Unable to get merge requests for project {project['id']}: {str(e)}")
            project_stats['errors'].append({
                'type': 'merge_requests',
                'error': str(e)
            })
        
        # 修改返回逻辑: 即使没有数据也返回结果
        return project_stats 