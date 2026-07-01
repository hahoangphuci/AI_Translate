from flask import Blueprint, jsonify, current_app

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/config', methods=['GET'])
def get_ai_config():
    cfg = current_app.config
    return jsonify({
        'provider': cfg.get('AI_PROVIDER'),
        'model': cfg.get('AI_MODEL'),
        'available_models': cfg.get('AI_AVAILABLE_MODELS'),
        'endpoints': cfg.get('AI_ENDPOINTS'),
        'headers': cfg.get('AI_HEADERS'),
        'has_api_key': bool(cfg.get('OPENROUTER_API_KEY'))
    }), 200

@ai_bp.route('/status', methods=['GET'])
def ai_status():
    cfg = current_app.config
    return jsonify({
        'has_api_key': bool(cfg.get('OPENROUTER_API_KEY')),
        'provider': cfg.get('AI_PROVIDER')
    }), 200
