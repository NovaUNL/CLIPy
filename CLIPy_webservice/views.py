from datetime import datetime
from flask import Blueprint, jsonify

from . import config
from CLIPy import Clip, CacheStorage

bp = Blueprint('clipy', __name__, url_prefix='')

storage = CacheStorage.postgresql(config.DB_USER, config.DB_PASSWORD, config.DB_NAME)
clip = Clip(storage, config.CLIP_USER, config.CLIP_PASSWORD)


@bp.route('/')
def index():
    return "The computer is computing!"


@bp.route('/buildings/', methods=['GET'])
def get_building():
    return jsonify(clip.list_buildings())


@bp.route('/departments/', methods=['GET'])
def get_departments():
    return jsonify(clip.list_departments())


@bp.route('/courses/', methods=['GET'])
def get_courses():
    return jsonify(clip.list_courses())


@bp.route('/students/', methods=['GET'])
def get_students():
    return jsonify(clip.list_students())


@bp.route('/departments/<int:department_id>', methods=['GET'])
def get_department(department_id):
    return jsonify(clip.get_department(department_id))


@bp.route('/library_occupation/<string:day>', methods=['GET'])
def get_library_info(day):
    date = datetime.strptime(day, "%Y-%m-%d").date()
    return jsonify({
        'individual': clip.fetch_library_individual_room_availability(date),
        'group': clip.fetch_library_group_room_availability(date)
    })
