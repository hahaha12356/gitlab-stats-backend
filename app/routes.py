from flask import Blueprint, request, jsonify
from .gitlab_client import GitLabClient
from .services import GitLabStatsService
import logging
import requests

api = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api.route('/stats', methods=['POST'])
def get_stats():
    try:
        data = request.json
        logger.debug(f"Received configuration: {data}")
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # 验证必要的字段
        required_fields = ['gitlab_url', 'private_token', 'group_id', 'start_date', 'end_date']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {missing_fields}'}), 400
        
        # 验证GitLab URL格式
        if not data['gitlab_url'].startswith(('http://', 'https://')):
            return jsonify({'error': 'GitLab URL must start with http:// or https://'}), 400
        
        logger.debug(f"Received request with GitLab URL: {data['gitlab_url']} and group ID: {data['group_id']}")
        
        gitlab_client = GitLabClient(
            data['gitlab_url'],
            data['private_token']
        )
        
        # 测试连接 - 尝试获取组项目
        try:
            projects = gitlab_client.get_group_projects(data['group_id'])
            if not projects:
                logger.error(f"No projects found in group {data['group_id']}")
                return jsonify({'error': f"No projects found in group {data['group_id']}"}), 404
            logger.debug(f"Successfully connected to GitLab and retrieved {len(projects)} projects")
        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else 500
            error_message = e.response.text if hasattr(e, 'response') and e.response else str(e)
            logger.error(f"Failed to connect to GitLab: {error_message}")
            
            if status_code == 401:
                return jsonify({'error': 'Invalid private token or unauthorized access'}), 401
            elif status_code == 404:
                return jsonify({'error': f"Group {data['group_id']} not found"}), 404
            else:
                return jsonify({'error': f'Failed to connect to GitLab: {error_message}'}), status_code
        
        try:
            service = GitLabStatsService(gitlab_client)
            stats = service.collect_stats(
                data['group_id'],
                data['start_date'],
                data['end_date']
            )
            return jsonify(stats)
        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else 500
            error_message = e.response.text if hasattr(e, 'response') and e.response else str(e)
            logger.error(f"Error collecting stats: {error_message}")
            return jsonify({'error': f'Error collecting stats: {error_message}'}), status_code
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500 