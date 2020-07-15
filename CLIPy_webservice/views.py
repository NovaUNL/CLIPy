from datetime import datetime
from flask import Blueprint, jsonify

from . import config
from CLIPy import Clip, CacheStorage

bp = Blueprint('clipy', __name__, url_prefix='')

storage = CacheStorage.postgresql(config.DB_USER, config.DB_PASSWORD, config.DB_NAME, host=config.DB_HOST)
clip = Clip(storage, config.CLIP_USER, config.CLIP_PASSWORD)


@bp.route('/')
def index():
    return "The computer is computing!"


@bp.route('/buildings/', methods=['GET'])
def get_building():
    return jsonify(clip.list_buildings())


@bp.route('/rooms/', methods=['GET'])
def get_rooms():
    return jsonify(clip.list_rooms())


@bp.route('/departments/', methods=['GET'])
def get_departments():
    return jsonify(clip.get_departments())


@bp.route('/courses/', methods=['GET'])
def get_courses():
    return jsonify(clip.list_courses())


@bp.route('/students/', methods=['GET'])
def get_students():
    return jsonify(clip.list_students())


@bp.route('/teachers/', methods=['GET'])
def get_teachers():
    return jsonify(clip.list_teachers())


@bp.route('/student/<int:student_id>', methods=['GET'])
def get_student(student_id):
    return jsonify(clip.get_student(student_id))


@bp.route('/department/<int:department_id>', methods=['GET'])
def get_department(department_id):
    return jsonify(clip.get_department(department_id))


@bp.route('/class/<int:class_id>', methods=['GET'])
def get_class(class_id):
    return jsonify(clip.get_class(class_id))


@bp.route('/class_inst/<int:instance_id>', methods=['GET'])
def get_class_instance(instance_id):
    return jsonify(clip.get_class_instance(instance_id))

@bp.route('/files/<int:instance_id>', methods=['GET'])
def get_files(instance_id):
    return jsonify(clip.get_class_instance_files(instance_id))


@bp.route('/turn/<int:turn_id>', methods=['GET'])
def get_turn(turn_id):
    return jsonify(clip.get_turn(turn_id))


@bp.route('/turn_inst/<int:turn_inst_id>', methods=['GET'])
def get_turn_instance(turn_inst_id):
    return jsonify(clip.get_turn_instance(turn_inst_id))


@bp.route('/enrollment/<int:enrollment_id>', methods=['GET'])
def get_enrollment(enrollment_id):
    return jsonify(clip.get_enrollment(enrollment_id))


@bp.route('/evaluation/<int:evaluation_id>', methods=['GET'])
def get_evaluation(evaluation_id):
    return jsonify(clip.get_evaluation(evaluation_id))


@bp.route('/library_occupation/<string:day>', methods=['GET'])
def get_library_info(day):
    date = datetime.strptime(day, "%Y-%m-%d").date()
    return jsonify({
        'individual': clip.fetch_library_individual_room_availability(date),
        'group': clip.fetch_library_group_room_availability(date)
    })


@bp.route('/update/classes/<int:institution_id>', methods=['GET'])
def update_classes(institution_id):
    clip.update_classes(institution_id)
    return "Success"


@bp.route('/update/teachers/<int:institution_id>', methods=['GET'])
def update_teachers(institution_id):
    clip.update_teachers(institution_id)
    return "Success"


@bp.route('/update/admissions/<int:institution_id>', methods=['GET'])
def update_admissions(institution_id):
    clip.update_admissions(institution_id)
    return "Success"


@bp.route('/update/class_info/<int:year>/<int:year_parts>/<int:part>', methods=['GET'])
def update_class_info(year, year_parts, part):
    clip.update_class_info(year, year_parts, part)
    return "Success"


@bp.route('/update/class_enrollments/<int:year>/<int:year_parts>/<int:part>', methods=['GET'])
def update_class_enrollments(year, year_parts, part):
    clip.update_class_enrollments(year, year_parts, part)
    return "Success"


@bp.route('/update/class_files/<int:year>/<int:year_parts>/<int:part>', methods=['GET'])
def update_class_files(year, year_parts, part):
    clip.update_class_files(year, year_parts, part)
    return "Success"


@bp.route('/update/turns/<int:year>/<int:year_parts>/<int:part>', methods=['GET'])
def update_turns(year, year_parts, part):
    clip.update_turns(year, year_parts, part)
    return "Success"
